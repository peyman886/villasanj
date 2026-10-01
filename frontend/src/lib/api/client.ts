/** Typed API client, generated from the backend's OpenAPI schema (`make openapi`). */

import createClient from "openapi-fetch";

import { apiBaseUrl } from "@/lib/health";

import type { components, paths } from "./schema";

export type Listing = components["schemas"]["ListingOut"];
export type Offer = components["schemas"]["OfferOut"];
export type CalendarNight = components["schemas"]["CalendarNightOut"];
export type Review = components["schemas"]["ReviewOut"];
export type Provenance = components["schemas"]["ProvenanceOut"];
export type Scenario = components["schemas"]["ScenarioOut"];

export function apiClient(baseUrl: string = apiBaseUrl(), fetchImpl?: typeof fetch) {
  return createClient<paths>({ baseUrl, ...(fetchImpl ? { fetch: fetchImpl } : {}) });
}
