export function makeResponse(resp) {
    return Promise.resolve({
        ...resp,
    });
}
/**
 * Loop through iterable one element at a time and await on async callback at every iteration
 */
export async function asyncLoopOneAtATime(things, cb) {
    const returnValues = [];
    for (const thing of things) {
        // eslint-disable-next-line no-await-in-loop
        returnValues.push(await cb(thing));
    }
    return returnValues;
}
/**
 * Loop through iterable in parallel
 * @param things
 * @param cb
 * @returns
 */
export async function asyncLoop(things, cb) {
    return Promise.all(things.map((t) => cb(t)));
}
//# sourceMappingURL=helpers.js.map