import _ from "lodash";
let _HISTORY_SERVICE = undefined;
/**
 * Keeps of lifecycle events in Sail.
 */
export class HistoryService {
    events;
    /**
     @deprecated
     */
    subscribers;
    subscribersv2;
    pause;
    static instance() {
        if (_.isUndefined(_HISTORY_SERVICE)) {
            _HISTORY_SERVICE = new HistoryService();
        }
        return _HISTORY_SERVICE;
    }
    constructor() {
        this.events = [];
        this.subscribers = {
            engine: [],
            src: [],
            extension: [],
            lspServer: [],
            apiServer: [],
            watcher: [],
            lookupProvider: [],
        };
        this.subscribersv2 = {
            engine: [],
            src: [],
            extension: [],
            lspServer: [],
            apiServer: [],
            watcher: [],
            lookupProvider: [],
        };
        this.pause = false;
    }
    add(event) {
        if (!this.pause) {
            this.events.unshift(event);
            this.subscribers[event.source].forEach((f) => f(event));
            this.subscribersv2[event.source].forEach(({ listener, id }) => {
                if (!event.id || event.id === id) {
                    listener(event);
                }
            });
        }
    }
    remove(id, source) {
        const idx = _.findIndex(this.subscribersv2[source], ({ id: subId }) => subId === id);
        if (idx >= 0) {
            this.subscribersv2[source].splice(idx, 1);
        }
    }
    clearSubscriptions() {
        this.subscribers = {
            engine: [],
            src: [],
            extension: [],
            lspServer: [],
            apiServer: [],
            watcher: [],
            lookupProvider: [],
        };
        this.subscribersv2 = {
            engine: [],
            src: [],
            extension: [],
            lspServer: [],
            apiServer: [],
            watcher: [],
            lookupProvider: [],
        };
    }
    lookBack(num = 3) {
        return this.events.slice(0, num);
    }
    subscribe(source, func) {
        this.subscribers[source].push(func);
    }
    subscribev2(source, ent) {
        this.subscribersv2[source].push(ent);
    }
}
//# sourceMappingURL=history.js.map