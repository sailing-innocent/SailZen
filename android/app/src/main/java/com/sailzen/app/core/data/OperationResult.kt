package com.sailzen.app.core.data

/**
 * 原子操作结果：一次后台交互对用户只呈现“成功”或“失败”。
 * Repository 用 Success 包裹服务端返回值，用 Failure 携带可读错误；
 * ViewModel 通过 onSuccess / onFailure 统一处理 UI 反馈与刷新。
 */
sealed class OperationResult<out T> {

    data class Success<T>(val data: T) : OperationResult<T>()

    data class Failure(val message: String, val cause: Throwable? = null) : OperationResult<Nothing>()

    fun isSuccess(): Boolean = this is Success

    fun isFailure(): Boolean = this is Failure

    fun getOrNull(): T? = (this as? Success<T>)?.data

    fun exceptionOrNull(): Throwable? = (this as? Failure)?.cause
}

/**
 * 执行挂起块，捕获异常并包装为 [OperationResult]。
 *
 * @param onSuccess 成功后触发的事件；不为 null 时，[DataChangeBus] 会广播该事件以驱动相关页面刷新。
 */
suspend inline fun <T> runOperation(
    bus: DataChangeBus,
    crossinline block: suspend () -> T,
    onSuccess: (T) -> DataChangeEvent? = { null },
): OperationResult<T> = try {
    val result = block()
    onSuccess(result)?.let { bus.emit(it) }
    OperationResult.Success(result)
} catch (e: Exception) {
    OperationResult.Failure(e.message ?: "操作失败", e)
}

inline fun <T> OperationResult<T>.onSuccess(action: (T) -> Unit): OperationResult<T> {
    if (this is OperationResult.Success) action(data)
    return this
}

inline fun <T> OperationResult<T>.onFailure(action: (OperationResult.Failure) -> Unit): OperationResult<T> {
    if (this is OperationResult.Failure) action(this)
    return this
}

inline fun <T, R> OperationResult<T>.map(transform: (T) -> R): OperationResult<R> = when (this) {
    is OperationResult.Success -> OperationResult.Success(transform(data))
    is OperationResult.Failure -> OperationResult.Failure(message, cause)
}
