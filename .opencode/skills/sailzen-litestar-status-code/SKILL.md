# Litestar 状态码与响应体冲突修复

## 问题描述

Litestar 框架中，某些 HTTP 状态码不支持响应体（response body）：
- 204 No Content
- 304 Not Modified  
- 任何低于 200 的状态码（如 1xx, 100 Continue 等）

当路由处理器返回数据但使用了这些状态码时，会报错：

```
A status code 204, 304 or in the range below 200 does not support a response body. 
If xxx.yyy.delete_file should return a value, change the route handler status code to an appropriate value.
```

## 常见场景

DELETE 请求默认返回 204 No Content，但如果代码返回了响应对象，就会触发错误。

## 修复方法

对于需要返回响应体的 DELETE/PUT/PATCH 请求，显式指定状态码为 200：

```python
# ❌ 错误 - 返回响应体但使用默认 204 状态码
@delete(path="/delete/{filename:str}")
async def delete_file(self, filename: str) -> FileDeleteResponse:
    ...
    return FileDeleteResponse(filename=filename, message="删除成功")

# ✅ 正确 - 显式指定 200 状态码以允许返回响应体
@delete(path="/delete/{filename:str}", status_code=200)
async def delete_file(self, filename: str) -> FileDeleteResponse:
    ...
    return FileDeleteResponse(filename=filename, message="删除成功")
```

## 最佳实践

1. **DELETE 请求**：
   - 如果不返回数据：使用默认 204
   - 如果需要返回确认信息：显式设置 `status_code=200`

2. **PUT/PATCH 请求**：
   - 通常返回 200 并携带更新后的资源

3. **创建资源（POST）**：
   - 通常返回 201 Created

## 参考

- Litestar 文档：[HTTP Route Handlers](https://docs.litestar.dev/2/usage/routing/handlers.html)
- HTTP 状态码规范：[RFC 7231](https://tools.ietf.org/html/rfc7231)

## 历史记录

- 2026-03-15: 修复 `FileStorageController.delete_file` 方法的 204/响应体冲突
