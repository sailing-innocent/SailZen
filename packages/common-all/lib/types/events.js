import { EventEmitter as NodeEventEmitter } from "events";
/**
 * An event emitter can be used to create and manage an {@link Event} for others
 * to subscribe to. One emitter always owns one event.
 *
 * This mimics the interface signature of vscode.EventEmitter but can be used
 * outside of plugin-core.
 */
export class EventEmitter {
    _emitter = new NodeEventEmitter();
    _EVENT_CHANNEL = "default";
    /**
     * The event listeners can subscribe to.
     */
    event = (listener, thisArgs) => {
        let callback = listener;
        if (thisArgs) {
            callback = callback.bind(thisArgs);
        }
        this._emitter.on(this._EVENT_CHANNEL, callback);
        const disposable = {
            dispose: () => {
                this._emitter.removeListener(this._EVENT_CHANNEL, callback);
            },
        };
        return disposable;
    };
    /**
     * Notify all subscribers of the {@link EventEmitter.event event}. Failure
     * of one or more listener will not fail this function call.
     *
     * @param data The event object.
     */
    fire(data) {
        this._emitter.emit(this._EVENT_CHANNEL, data);
    }
    /**
     * Dispose this object and free resources.
     */
    dispose() {
        this._emitter.removeAllListeners(this._EVENT_CHANNEL);
    }
}
//# sourceMappingURL=events.js.map