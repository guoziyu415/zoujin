// Telemetry events waiting to be sent (frontend-design 11, data-design 9.3; types from packages/contracts). F-2c only
// queues them; F-0's network layer drains the queue in batches of up to 50 to POST /v1/telemetry with the common
// properties, and with sendBeacon when the page is hidden.
import type { Api } from "@zoujin/contracts";

type Event = Api.TelemetryEvent;
type Name = Event["name"];
type PropsOf<N extends Name> = Extract<Event, { name: N }>["props"];

const MAX_QUEUED = 500; // nobody draining (no network layer yet, or offline for long): keep the newest

const queue: Event[] = [];

export function track<N extends Name>(name: N, props: PropsOf<N>): void {
  queue.push({
    name,
    clientTs: new Date().toISOString(),
    props,
  } as Extract<Event, { name: N }>);
  if (queue.length > MAX_QUEUED) queue.splice(0, queue.length - MAX_QUEUED);
}

// up to n of the oldest events, removed from the queue
export function drain(n = 50): Event[] {
  return queue.splice(0, n);
}

// what is waiting, without removing it (the test hook and the measuring page)
export function peek(): readonly Event[] {
  return queue;
}
