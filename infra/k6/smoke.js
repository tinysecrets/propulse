import http from "k6/http";
import { check, sleep } from "k6";

export const options = {
  stages: [
    { duration: "20s", target: 50 },
    { duration: "30s", target: 200 },
    { duration: "20s", target: 0 },
  ],
  thresholds: {
    http_req_failed: ["rate<0.01"],
    "http_req_duration{route:config}": ["p(95)<150"],
  },
};

const BASE = __ENV.BASE_URL || "http://localhost:8080";
const KEY = __ENV.PP_PUB_KEY || "";

export default function () {
  const res = http.post(`${BASE}/v1/config`, null, {
    headers: { "x-pp-key": KEY },
    tags: { route: "config" },
  });
  check(res, { "config responds": (r) => r.status === 200 || r.status === 401 });

  const source = http.get(`${BASE}/source`, { tags: { route: "source" } });
  check(source, {
    "agpl disclosure": (r) => r.status === 200 && r.body.includes("AGPL"),
  });

  const plans = http.get(`${BASE}/v1/billing/plans`, { tags: { route: "plans" } });
  check(plans, { "plans served": (r) => r.status === 200 });

  sleep(0.2);
}
