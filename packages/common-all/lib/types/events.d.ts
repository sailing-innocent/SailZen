import { Disposable } from "./compat";
import { EventEmitter as NodeEventEmitter } from "events";
/**
 * Represents a typed event that can be subscribed to.
 *
 * This has an indentical interface signature to vscode.Event, but can be used
 * outside of plugin-core.
 */
export interface Event<T> {
    /**
     * A function that represents an event to which you subscribe by calling it with
     * a listener function as argument.
     *
     * @param listener The listener function will be called when the event happens.
     * @param thisArgs The `this`-argument which will be used when calling the event listener.
     */
    (listener: (e: T) => any, thisArgs?: any): Disposable;
}
/**
 * An event emitter can be used to create and manage an {@link Event} for others
 * to subscribe to. One emitter always owns one event.
 *
 * This mimics the interface signature of vscode.EventEmitter but can be used
 * outside of plugin-core.
 */
export declare class EventEmitter<T> {
    _emitter: NodeEventEmitter;
    _EVENT_CHANNEL: string;
    /**
     * The event listeners can subscribe to.
     */
    event: Event<T>;
    /**
     * Notify all subscribers of the {@link EventEmitter.event event}. Failure
     * of one or more listener will not fail this function call.
     *
     * @param data The event object.
     */
    fire(data: T): void;
    /**
     * Dispose this object and free resources.
     */
    dispose(): void;
}
