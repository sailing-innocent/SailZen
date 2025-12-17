import { ZDOCTAG_REGEX, ZDOCTAG_REGEX_LOOSE } from "./zdocTags";

describe("ZDOCTAG_REGEX", () => {
  test("\\cite{hello} is matched ", () => {
    const match = ZDOCTAG_REGEX.exec("\\cite{hello}");
    expect(match).not.toBeNull();
    expect(match?.groups?.tagContents).toBe("hello");
  });

  test("\\cite{hello} is matched loose ", () => {
    const match = ZDOCTAG_REGEX_LOOSE.exec("\\cite{hello}");
    expect(match).not.toBeNull();
    // console.log(match);
    expect(match?.groups?.zdocTagContents).toBe("hello");
  });

  test("\\cite{hello} is matched loose repeat", () => {
    ZDOCTAG_REGEX_LOOSE.lastIndex = 0; // after first match, the regex state is changed
    const match = ZDOCTAG_REGEX_LOOSE.exec("\\cite{hello}");
    console.log(match); // Why is this null?
    expect(match).not.toBeNull();
    expect(1).toBe(1); // Placeholder to avoid empty test

    const strmatch = "what \\cite{hello} blablabla".match(ZDOCTAG_REGEX_LOOSE);
    expect(strmatch).not.toBeNull();
    console.log(strmatch);
    // expect(strmatch?.groups?.ZDOCTAGContents).toBe("hello");
  });
});
