# 天气联动设计

将 daily journal 笔记中的天气元素与远程 sail_server 联动：服务端定期拉取
Open-Meteo 天气并写入 `days.ref["weather"]`，VSCode 插件按 journal 笔记日期
渲染**那一天**的天气卡片。

## 数据流

```
Open-Meteo API ──定时拉取──▶ sail_server (days.ref["weather"])
                                  │ GET /api/v1/life/weather?date=YYYY-MM-DD
                                  ▼
                          VSCode 插件 weatherCore
                          （按 journal 日期渲染天气卡片）
```

## 存储模型

不建表、无迁移：天气整体存入 Day ORM 的 JSONB `ref["weather"]`。

```jsonc
{
  "weather": {
    "updated_at": "2026-07-18T08:30:00+08:00",
    "cities": {
      "杭州": {
        "kind": "record",              // forecast=逐步更新的预报 | record=固化实录（不可变）
        "weather_code": 61,
        "temp_max": 33.5, "temp_min": 26.1,
        "temp_current": null,          // 仅 forecast 且为今天时可能有值
        "humidity": null, "wind_speed": null,
        "source": "open-meteo-archive",
        "fetched_at": "2026-07-19T00:10:00+08:00"
      }
    }
  }
  // ref 其他 key 原样保留（get → merge → assign，整体重赋值触发 JSONB 变更检测）
}
```

## 固化策略（每次更新循环 / 每城市）

1. 拉 forecast（默认 7 天），`[today, today+N)` 逐日覆盖写 `kind=forecast`。
2. `[today-lookback, today-1]`（默认 3 天）内仍非 record 的日期补拉 archive，
   写入 `kind=record` —— 当天过去后留下天气记录；record 永不被覆盖。
3. 单城市失败只记日志与 errors；时区统一 Asia/Shanghai。

## API 概览

```
GET  /api/v1/life/weather?date=YYYY-MM-DD   # 查询某日天气（date 缺省今天；无数据 available=false, HTTP 200）
POST /api/v1/life/weather/refresh           # 手动触发一次更新循环，返回统计
```

## 服务端模块

| 文件 | 说明 |
|------|------|
| `sail_server/application/dto/weather.py` | CityWeather / DayWeatherResponse / WeatherRefreshResponse |
| `sail_server/utils/weather.py` | Open-Meteo async 客户端（forecast / archive） |
| `sail_server/model/weather.py` | 查询 / 更新 / record 固化 / `weather_update_loop` 后台循环 / env 配置 |
| `sail_server/controller/weather.py` | WeatherController |
| `server.py` | startup 启动循环（`WEATHER_ENABLED`）、shutdown 取消 |

## 插件模块

| 文件 | 说明 |
|------|------|
| `features/pageElements/weatherCore.ts` | vscode 无关核心：sail_server client / 按日期缓存 / provider 工厂 / 卡片渲染（零运行时依赖，类型级引用 unified） |
| `features/pageElements/weatherPageElement.ts` | vscode 胶水层：读 `sailzen.sailServer.*` 配置、接 Logger、注册 provider |
| `server.ts` | prod engine 子进程注册（`SAIL_SERVER_URL` env） |
| `package.json` | `sailzen.sailServer.baseUrl` / `sailzen.sailServer.weatherCacheTtlMinutes` 配置项 |

## 缓存层级（均按日期/note 隔离，不会串日期）

1. weatherCore 模块级 cache：`${baseUrl}|${date}` 键；record 8×TTL；error 不缓存。
2. PageElementRegistry `cacheTtlMs`：键含 `note.id:contentHash:args`。
3. webview/engine 渲染缓存：同一笔记内容未变时复用旧 HTML（既有语义），
   天气更新在 TTL（默认 30min）后或重开 preview 时反映。

## 环境变量

见 `.env.template`：`WEATHER_ENABLED` / `WEATHER_UPDATE_INTERVAL_MINUTES` /
`WEATHER_FORECAST_DAYS` / `WEATHER_RECORD_LOOKBACK_DAYS` / `WEATHER_CITIES`。

## 验收要点

- `POST refresh` 无 errors；今天 → forecast，昨天 → record；`day/by-date` 中
  `ref.weather` 已写入且其他 ref key 不受影响。
- 打开不同日期 journal，preview 随 focus 切换显示对应日期天气（预报/实录角标）。
- 断网/停服时卡片显示"获取失败"柔和提示而非错误框；恢复后 TTL 过期自动复原。
