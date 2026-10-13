"""Probabilistic LSTM forecaster: learns what "normal" activity looks like for the household.

At each 5-minute step the network receives the activity of the previous window and the
calendar context (hour, weekday) of the current window. It predicts, for the current window,
an expected *rate* for each count (Poisson distribution: residents, guests, unknown people,
animals...) and a probability for the door being open (Bernoulli distribution).

The anomaly score is the "surprise" of what was actually observed: its negative
log-likelihood under the prediction. Seeing someone at 3 a.m., when the expected rate is close
to zero, is very surprising; seeing a resident at 7 p.m. is not.

Design notes
* Forecaster, not autoencoder: an autoencoder is shown the window it must reconstruct and
  learns to copy it, anomalies included. A forecaster never sees the window it scores.
* Poisson/Bernoulli likelihoods instead of mean squared error: events are sparse counts; with
  MSE the model just predicts "zero everywhere" and rare but meaningful events get drowned.
"""

from __future__ import annotations

import torch
import torch.nn.functional as F  # noqa: N812
from torch import nn

from app.anomaly.features import CONTEXT_FEATURES, COUNT_FEATURES, TARGET_FEATURES

_TARGETS = list(TARGET_FEATURES)
_CONTEXT = list(CONTEXT_FEATURES)
_N_COUNTS = len(COUNT_FEATURES)  # the last target is the door state


class LSTMForecaster(nn.Module):
    def __init__(
        self,
        n_features: int,
        n_targets: int = len(TARGET_FEATURES),
        hidden_size: int = 64,
        num_layers: int = 1,
        dropout: float = 0.0,
    ) -> None:
        super().__init__()
        self.lstm = nn.LSTM(
            n_features,
            hidden_size,
            num_layers,
            batch_first=True,
            dropout=dropout if num_layers > 1 else 0.0,
        )
        self.head = nn.Sequential(
            nn.Linear(hidden_size, hidden_size), nn.ReLU(), nn.Linear(hidden_size, n_targets)
        )

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        """x: (batch, time, features) -> (batch, time, targets): log-rates then door logit."""
        output, _ = self.lstm(x)
        return self.head(output)


def to_inputs_targets(scaled: torch.Tensor, raw: torch.Tensor) -> tuple[torch.Tensor, torch.Tensor]:
    """Build model inputs and targets from T+1 consecutive windows.

    Input at step t  = scaled activity of window t-1 + calendar context of window t.
    Target at step t = raw activity of window t (counts and door state).
    """
    inputs = torch.cat([scaled[:, :-1, _TARGETS], scaled[:, 1:, _CONTEXT]], dim=-1)
    return inputs, raw[:, 1:, _TARGETS]


def surprise(outputs: torch.Tensor, targets: torch.Tensor) -> torch.Tensor:
    """Negative log-likelihood of each observed target, shape (batch, time, targets)."""
    log_rate = outputs[..., :_N_COUNTS].clamp(-15, 8)
    counts = targets[..., :_N_COUNTS]
    poisson = torch.exp(log_rate) - counts * log_rate + torch.lgamma(counts + 1)
    door = F.binary_cross_entropy_with_logits(
        outputs[..., _N_COUNTS], targets[..., _N_COUNTS], reduction="none"
    )
    return torch.cat([poisson, door.unsqueeze(-1)], dim=-1)


@torch.no_grad()
def compute_surprise(
    model: LSTMForecaster, scaled: torch.Tensor, raw: torch.Tensor
) -> torch.Tensor:
    model.eval()
    inputs, targets = to_inputs_targets(scaled, raw)
    return surprise(model(inputs), targets)


def anomaly_scores(surprises: torch.Tensor, horizon: int) -> torch.Tensor:
    """Mean total surprise over the most recent `horizon` windows.

    Averaging over a few windows (15 min by default) lets sustained unusual activity build
    up a high score while a single noisy detection stays low. Training, evaluation and live
    inference all use this one definition.
    """
    return surprises[:, -horizon:, :].sum(dim=-1).mean(dim=-1)
