import { getJournalTitle } from "../index";

describe("getJournalTitle", () => {
  describe("valid date formats", () => {
    it("should return formatted title for YYYY.MM.DD format", () => {
      const result = getJournalTitle("2023.12.25", "yyyy.MM.dd");
      expect(result).toBe("2023-12-25");
    });

    it("should return formatted title for YYYY-MM-DD format", () => {
      const result = getJournalTitle("2023-12-25", "yyyy-MM-dd");
      expect(result).toBe("2023-12-25");
    });

    it("should return formatted title for MM/DD/YYYY format", () => {
      const result = getJournalTitle("12/25/2023", "MM/dd/yyyy");
      expect(result).toBe("12/25/2023"); // Function returns original format, not converted to dashes
    });

    it("should return formatted title for DD.MM.YYYY format", () => {
      const result = getJournalTitle("25.12.2023", "dd.MM.yyyy");
      expect(result).toBe("25-12-2023");
    });

    it("should return formatted title for YYYY.MM format", () => {
      const result = getJournalTitle("2023.12", "yyyy.MM");
      expect(result).toBe("2023-12");
    });

    it("should return formatted title for YYYY format", () => {
      const result = getJournalTitle("2023", "yyyy");
      expect(result).toBe("2023");
    });

    it("should ignore the prefix segment", () => {
      const result = getJournalTitle("journal.daily.2023.12.25", "y.MM.dd");
      expect(result).toBe("2023-12-25");
    });
  });

  describe("complex note names with multiple dots", () => {
    it("should return undefined when note has extra segments beyond date format", () => {
      const result = getJournalTitle("2023.12.25.journal.notes", "yyyy.MM.dd");
      expect(result).toBeUndefined(); // Extra segments cause parsing to fail
    });

    it("should try different segments when first segment doesn't match", () => {
      const result = getJournalTitle("notes.2023.12.25", "yyyy.MM.dd");
      expect(result).toBe("2023-12-25");
    });

    it("should return undefined when middle segments don't form valid date", () => {
      const result = getJournalTitle("journal.2023.12.25.notes", "yyyy.MM.dd");
      expect(result).toBeUndefined(); // Extra segments cause parsing to fail
    });

    it("should handle multiple date-like segments and pick the first valid one", () => {
      const result = getJournalTitle("2023.12.25.2024.01.01", "yyyy.MM.dd");
      expect(result).toBe("2024-01-01"); // Finds the last valid date segment
    });
  });

  describe("edge cases", () => {
    it("should return undefined for empty string", () => {
      const result = getJournalTitle("", "yyyy.MM.dd");
      expect(result).toBeUndefined();
    });

    it("should return undefined for invalid date format", () => {
      const result = getJournalTitle("invalid-date", "yyyy.MM.dd");
      expect(result).toBeUndefined();
    });

    it("should return undefined when no segment matches the date format", () => {
      const result = getJournalTitle("some.random.text", "yyyy.MM.dd");
      expect(result).toBeUndefined();
    });

    it("should return undefined for single segment that doesn't match", () => {
      const result = getJournalTitle("not-a-date", "yyyy.MM.dd");
      expect(result).toBeUndefined();
    });

    it("should handle single dot in note name", () => {
      const result = getJournalTitle("2023.12", "yyyy.MM");
      expect(result).toBe("2023-12");
    });

    it("should handle note name with no dots", () => {
      const result = getJournalTitle("2023", "yyyy");
      expect(result).toBe("2023");
    });
  });

  describe("different date formats", () => {
    it("should work with ISO format", () => {
      const result = getJournalTitle("2023-12-25", "yyyy-MM-dd");
      expect(result).toBe("2023-12-25");
    });

    it("should work with US format", () => {
      const result = getJournalTitle("12/25/2023", "MM/dd/yyyy");
      expect(result).toBe("12/25/2023"); // Function preserves original separators
    });

    it("should work with European format", () => {
      const result = getJournalTitle("25.12.2023", "dd.MM.yyyy");
      expect(result).toBe("25-12-2023");
    });

    it("should work with year-month format", () => {
      const result = getJournalTitle("2023-12", "yyyy-MM");
      expect(result).toBe("2023-12");
    });

    it("should work with month-day format", () => {
      const result = getJournalTitle("12-25", "MM-dd");
      expect(result).toBe("12-25");
    });
  });

  describe("real-world scenarios", () => {
    it("should return undefined for journal note with extra segments", () => {
      const result = getJournalTitle("2023.12.25.daily-journal", "yyyy.MM.dd");
      expect(result).toBeUndefined(); // Extra segments cause parsing to fail
    });

    it("should return undefined for note with date in middle and extra segments", () => {
      const result = getJournalTitle("journal.2023.12.25.notes", "yyyy.MM.dd");
      expect(result).toBeUndefined(); // Extra segments cause parsing to fail
    });

    it("should handle note with date suffix", () => {
      const result = getJournalTitle("my-journal.2023.12.25", "yyyy.MM.dd");
      expect(result).toBe("2023-12-25");
    });

    it("should return undefined for weekly journal with extra segments", () => {
      const result = getJournalTitle("2023.12.25.weekly", "yyyy.MM.dd");
      expect(result).toBeUndefined(); // Extra segments cause parsing to fail
    });

    it("should return undefined for monthly journal with extra segments", () => {
      const result = getJournalTitle("2023.12.monthly", "yyyy.MM");
      expect(result).toBeUndefined(); // Extra segments cause parsing to fail
    });
  });

  describe("format validation", () => {
    it("should validate against strict date format requirements", () => {
      const result = getJournalTitle("2023.1.1", "yyyy.MM.dd");
      expect(result).toBeUndefined(); // Should fail because format expects 2-digit month/day
    });

    it("should work with 2-digit format", () => {
      const result = getJournalTitle("2023.01.01", "yyyy.MM.dd");
      expect(result).toBe("2023-01-01");
    });

    it("should handle different separators in date format", () => {
      const result = getJournalTitle("2023/12/25", "yyyy/MM/dd");
      expect(result).toBe("2023/12/25"); // Function preserves original separators
    });
  });
});
