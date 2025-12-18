/**
 * Tests for ZDoc tag regex patterns
 */
import { ZDOCTAG_REGEX, ZDOCTAG_REGEX_LOOSE } from "../zdocTags";

describe("ZDOCTAG_REGEX", () => {
  test("\\cite{hello} is matched", () => {
    const match = ZDOCTAG_REGEX.exec("\\cite{hello}");
    expect(match).not.toBeNull();
    expect(match?.groups?.tagContents).toBe("hello");
  });

  test("\\cite{hello} is matched loose", () => {
    const match = ZDOCTAG_REGEX_LOOSE.exec("\\cite{hello}");
    expect(match).not.toBeNull();
    expect(match?.groups?.zdocTagContents).toBe("hello");
  });

  test("\\cite{hello} is matched loose in context", () => {
    const strmatch = "what \\cite{hello} blablabla".match(ZDOCTAG_REGEX_LOOSE);
    expect(strmatch).not.toBeNull();
  });
});
