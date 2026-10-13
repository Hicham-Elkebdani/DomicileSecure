/* DomicileSecure service worker: receives Web Push notifications from the API. */

self.addEventListener("push", (event) => {
  let payload = { title: "DomicileSecure", body: "Nouvelle notification", url: "/" };
  try {
    payload = { ...payload, ...event.data.json() };
  } catch {
    /* keep defaults */
  }
  const urgent = payload.severity === "high" || payload.severity === "critical";
  event.waitUntil(
    self.registration.showNotification(payload.title, {
      body: payload.body,
      icon: "/icon.svg",
      badge: "/icon.svg",
      tag: payload.tag,
      renotify: Boolean(payload.tag),
      requireInteraction: urgent,
      data: { url: payload.url || "/" },
    }),
  );
});

self.addEventListener("notificationclick", (event) => {
  event.notification.close();
  const target = new URL(event.notification.data?.url || "/", self.location.origin).href;
  event.waitUntil(
    self.clients.matchAll({ type: "window", includeUncontrolled: true }).then((clients) => {
      for (const client of clients) {
        if (client.url.startsWith(self.location.origin) && "focus" in client) {
          client.navigate(target);
          return client.focus();
        }
      }
      return self.clients.openWindow(target);
    }),
  );
});
