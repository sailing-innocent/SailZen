import levenshtein from "fast-levenshtein";
import { CONSTANTS } from "../constants";

/**
 * Returns levenshtein distance between the two strings, the higher the number
 * the further apart the strings are. 0 signals that the strings are equal. */
export function levenshteinDistance(s1: string, s2: string): number {
  return levenshtein.get(s1, s2);
}

export function parseDendronURI(linkString: string) {
  if (linkString.startsWith(CONSTANTS.SRC_DELIMITER)) {
    return {
      link: linkString.replace(CONSTANTS.SRC_DELIMITER, "http://175.27.233.235:4399/content?content="),
    }
  }
  if (linkString.startsWith(CONSTANTS.DENDRON_DELIMETER)) {
    const [vaultName, link] = linkString
      .split(CONSTANTS.DENDRON_DELIMETER)[1]
      .split("/");
    return {
      vaultName,
      link,
    };
  }
  return {
    link: linkString,
  };
}
