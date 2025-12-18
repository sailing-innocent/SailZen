export const matchAll = (
  pattern: RegExp,
  text: string
): Array<RegExpMatchArray> => {
  let match: RegExpMatchArray | null;
  const out: RegExpMatchArray[] = [];

  pattern.lastIndex = 0;

  // eslint-disable-next-line no-cond-assign
  while ((match = pattern.exec(text))) {
    out.push(match);
  }

  return out;
};

/**
 * Calculate the similarity between two strings using Dice's Coefficient
 * (Sørensen–Dice coefficient).
 *
 * This function returns a fraction between 0 and 1, where:
 * - 0 indicates completely different strings
 * - 1 indicates identical strings
 *
 * The algorithm works by:
 * 1. Converting both strings to bigrams (pairs of adjacent characters)
 * 2. Calculating the intersection and union of bigrams
 * 3. Returning: 2 * |intersection| / (|str1 bigrams| + |str2 bigrams|)
 *
 * @param str1 First string to compare
 * @param str2 Second string to compare
 * @returns Similarity score between 0 and 1
 */
export function compareTwoStrings(str1: string, str2: string): number {
  // If both strings are empty, they are identical
  if (str1.length === 0 && str2.length === 0) {
    return 1;
  }

  // If one string is empty and the other is not, they are completely different
  if (str1.length === 0 || str2.length === 0) {
    return 0;
  }

  // If both strings are identical, return 1
  if (str1 === str2) {
    return 1;
  }

  // Convert strings to bigrams (pairs of adjacent characters)
  const getBigrams = (str: string): Map<string, number> => {
    const bigrams = new Map<string, number>();
    for (let i = 0; i < str.length - 1; i++) {
      const bigram = str.substring(i, i + 2);
      bigrams.set(bigram, (bigrams.get(bigram) || 0) + 1);
    }
    return bigrams;
  };

  const str1Lower = str1.toLowerCase();
  const str2Lower = str2.toLowerCase();

  const bigrams1 = getBigrams(str1Lower);
  const bigrams2 = getBigrams(str2Lower);

  // Calculate intersection (common bigrams)
  // For each bigram in str1, count how many times it appears in both strings
  let intersection = 0;
  for (const [bigram, count1] of bigrams1.entries()) {
    const count2 = bigrams2.get(bigram) || 0;
    intersection += Math.min(count1, count2);
  }

  // Calculate Dice's Coefficient
  // Formula: 2 * |intersection| / (|bigrams1| + |bigrams2|)
  // |bigrams| = string length - 1 (number of adjacent character pairs)
  const totalBigrams1 = str1Lower.length > 1 ? str1Lower.length - 1 : 0;
  const totalBigrams2 = str2Lower.length > 1 ? str2Lower.length - 1 : 0;
  const union = totalBigrams1 + totalBigrams2;

  if (union === 0) {
    // Both strings are single characters
    // If they're the same (case-insensitive), return 1, otherwise 0
    return str1Lower === str2Lower ? 1 : 0;
  }

  return (2 * intersection) / union;
}
