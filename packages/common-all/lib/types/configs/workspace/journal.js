import { NoteAddBehaviorEnum } from "./types";
// const assertion to tell the compiler that we only want these as dayOfWeekNumber.
const possibleDayOfWeekNumber = [0, 1, 2, 3, 4, 5, 6];
/**
 * Generates default {@link JournalConfig}
 * @returns JouranlConfig
 */
export function genDefaultJournalConfig() {
    return {
        dailyDomain: "daily",
        name: "journal",
        dateFormat: "y.MM.dd",
        addBehavior: NoteAddBehaviorEnum.childOfDomain,
        // firstDayOfWeek: 1,
    };
}
//# sourceMappingURL=journal.js.map