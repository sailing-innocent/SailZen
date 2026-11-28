/**
 *  Performance timer utility class to make it easier to quickly add performance
 *  logging to code without having to add lots of variables to track timing state.
 *
 *  Usage example:
 *  const pt = PerformanceTimer();
 *
 *  pt.before('someFunc');
 *  someFunc();
 *  pt.after('someFunc');
 *
 *  pt.before('someOtherFunc');
 *  someOtherFunc();
 *  pt.after('someOtherFunc');
 *
 *  log.info({msg: pt.report()});
 *  */
export declare class PerformanceTimer {
    /** Before stamps in milliseconds. */
    private readonly beforeStampsMillis;
    private readonly timingsMillis;
    private readonly errors;
    private readonly opts?;
    constructor(opts?: {
        timerName: string;
    });
    before(name: string): void;
    after(name: string): void;
    report(): string;
}
