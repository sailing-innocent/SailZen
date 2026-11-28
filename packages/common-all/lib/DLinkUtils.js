import _ from "lodash";
export class DLinkUtils {
    static isEquivalent(linkA, linkB) {
        return (linkA.type === linkB.type &&
            this.isDLocEquivalent(linkA.from, linkB.from) &&
            this.isDLocEquivalent(linkA.to, linkB.to) &&
            linkA.value === linkB.value &&
            this.isPositionEquivalent(linkA.position, linkB.position));
    }
    static isDLocEquivalent(locA, locB) {
        if (!locA && !locB)
            return true;
        if (locA && locB) {
            return (locA.fname === locB.fname &&
                locA.id === locB.id &&
                locA.vaultName === locB.vaultName);
        }
        return false;
    }
    static isPositionEquivalent(posA, posB) {
        if (!posA && !posB)
            return true;
        if (posA && posB) {
            return (posA.start.line === posB.start.line &&
                posA.start.column === posB.start.column &&
                posA.end.line === posB.end.line &&
                posA.end.column === posB.end.column &&
                _.isEqual(posA.indent, posB.indent));
        }
        return false;
    }
}
//# sourceMappingURL=DLinkUtils.js.map