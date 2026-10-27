import { describe, expect, it } from "vitest";
import { allErrorCodes, errorForCode } from "./errors";
describe("API error messages", () => {
  it.each(allErrorCodes())("maps %s to a friendly next step", (code) => {
    const result = errorForCode(code); expect(result.message.length).toBeGreaterThan(8); expect(result.action.length).toBeGreaterThan(5);
  });
  it("falls back for future error codes", () => expect(errorForCode("NOT_YET_DEFINED").message).toBe(errorForCode("UNKNOWN_ERROR").message));
});
