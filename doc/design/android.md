# SailZen Android 客户端设计方案 (React Native)

## 文档信息

- **版本**: 2.0
- **日期**: 2026-03-01
- **状态**: 设计阶段
- **作者**: AI Agent

---

## 1. 项目背景与目标

### 1.1 现状分析

SailZen 目前已有：
- **sail_server**: Python + Litestar 后端 API
- **packages/site**: React + TypeScript Web 前端
- **文本分析系统**: LLM 驱动的作品分析、人物档案、设定管理、大纲提取

### 1.2 浏览器端 LLM 交互痛点

| 痛点 | 描述 | 影响 |
|------|------|------|
| **网络限制** | 浏览器 CORS 策略、企业防火墙限制 LLM API 调用 | 无法直接调用外部 LLM |
| **移动端体验** | Web 端在移动设备上交互受限 | 操作不便、性能受限 |
| **后台处理** | 页面关闭后分析任务中断 | 长时间分析不可靠 |
| **离线能力** | 无法离线阅读和分析 | 网络不稳定时不可用 |
| **系统集成** | 无法使用系统级分享、推送等功能 | 用户体验割裂 |

### 1.3 团队技术选型决策

**选择 React Native (而非原生 Kotlin)** 的理由：

| 考量因素 | React Native 优势 |
|----------|-------------------|
| **团队经验** | 复用现有 TypeScript/React 经验，降低学习成本 |
| **代码复用** | 与 packages/site 共享 types、hooks、utils，最大复用率可达 70% |
| **LLM 调用** | 原生 HTTP fetch，无 CORS 限制，直接调用 Moonshot/OpenAI/Gemini |
| **性能可接受** | 项目个人使用，不兼容低端机，性能非瓶颈 |
| **开发效率** | Hot Reload、OTA 更新，快速迭代 |

---

## 2. 技术选型

### 2.1 核心架构决策

| 技术决策 | 选择 | 理由 |
|----------|------|------|
| **框架** | React Native + Expo (Managed Workflow) | 最快启动、丰富生态、OTA 更新 |
| **语言** | TypeScript | 与 Web 端保持一致，类型安全 |
| **状态管理** | Zustand | Web 端已使用，保持一致 |
| **导航** | React Navigation v7 | 社区标准，Expo 兼容 |
| **HTTP 客户端** | axios + fetch | LLM 调用需自定义配置 |
| **本地存储** | MMKV (key-value) + WatermelonDB (复杂数据) | 高性能、离线优先 |
| **后台任务** | expo-background-fetch + expo-task-manager | 分析任务后台运行 |
| **推送通知** | expo-notifications | 任务完成推送 |

### 2.2 Expo Managed vs Bare Workflow

**选择 Expo Managed Workflow**，理由：
- ✅ 无需配置 Xcode/Android Studio 即可运行
- ✅ 内置 OTA (Over-The-Air) 更新能力
- ✅ 统一 API 层（Camera、Storage、Notifications 等）
- ✅ EAS Build 云端构建，无需本地配置
- ✅ 2024+ 的 New Architecture 性能接近原生

**当需要 Eject 时**（预留方案）：
- 需要自定义原生模块（如特殊的 LLM 本地推理）
- 需要深度系统权限
- Expo SDK 不满足需求

### 2.3 技术架构

```
┌─────────────────────────────────────────────────────────────────────┐
│                         表现层 (UI Layer)                            │
├─────────────────────────────────────────────────────────────────────┤
│  React Native + Expo                                                │
│  ├── 页面: 作品列表、章节阅读、任务管理、人物档案                      │
│  ├── 组件: 共享 @saili/ui 组件 (平台适配 .native.tsx)                │
│  └── 导航: React Navigation (Bottom Tabs + Stack)                   │
└─────────────────────────────────────────────────────────────────────┘
                                  │
                                  ▼
┌─────────────────────────────────────────────────────────────────────┐
│                      业务逻辑层 (Hooks/Stores)                        │
├─────────────────────────────────────────────────────────────────────┤
│  ├── 作品管理: useWorks (复用自 packages/site)                       │
│  ├── 分析任务: useAnalysisTask + Zustand Store                       │
│  ├── 阅读器: useReader (本地进度管理)                                │
│  └── LLM 服务: useLLM (直接调用 API，无 CORS)                         │
└─────────────────────────────────────────────────────────────────────┘
                                  │
                                  ▼
┌─────────────────────────────────────────────────────────────────────┐
│                        数据层 (Data Layer)                           │
├─────────────────────────────────────────────────────────────────────┤
│  ├── 网络数据源: axios                                               │
│  │   ├── sail_server API (/api/v1/*)                                │
│  │   └── LLM API (Moonshot/OpenAI/Gemini) ← 直接调用，无 CORS 限制    │
│  ├── 本地数据源: WatermelonDB (SQLite)                               │
│  │   ├── 章节缓存 (chapters)                                        │
│  │   ├── 分析结果 (analysis_results)                                │
│  │   └── 阅读进度 (reading_progress)                                │
│  └── 快速存储: MMKV (settings, tokens)                              │
└─────────────────────────────────────────────────────────────────────┘
                                  │
                                  ▼
┌─────────────────────────────────────────────────────────────────────┐
│                        系统服务层 (Services)                         │
├─────────────────────────────────────────────────────────────────────┤
│  ├── 后台任务: expo-background-fetch (分析任务轮询)                   │
│  ├── 推送通知: expo-notifications (任务完成通知)                      │
│  ├── 网络监听: @react-native-community/netinfo                       │
│  └── 文件系统: expo-file-system (章节内容离线缓存)                    │
└─────────────────────────────────────────────────────────────────────┘
```

---

## 3. Monorepo 集成设计

### 3.1 目录结构

```
SailZen/                           # 项目根
├── packages/
│   ├── site/                      # Web 前端 (已存在)
│   ├── mobile/                    # React Native App (新增) ⭐
│   │   ├── App.tsx
│   │   ├── app.json               # Expo 配置
│   │   ├── eas.json               # EAS Build 配置
│   │   ├── src/
│   │   │   ├── api/               # API 客户端 (复用自 site)
│   │   │   ├── components/        # 移动端特有组件
│   │   │   ├── hooks/             # 共享/特有 hooks
│   │   │   ├── navigation/        # 路由配置
│   │   │   ├── screens/           # 页面
│   │   │   ├── services/          # LLM 服务等
│   │   │   ├── stores/            # Zustand stores
│   │   │   └── utils/             # 工具函数
│   │   └── package.json
│   │
│   ├── common-all/                # 共享类型和常量 (已存在)
│   │   └── src/
│   │       ├── types/
│   │       │   ├── analysis.ts    # 分析相关类型
│   │       │   ├── text.ts        # 文本管理类型
│   │       │   └── ...
│   │       └── utils/
│   │
│   └── ui/                        # 共享 UI 组件 (新增)
│       ├── src/
│       │   ├── components/
│       │   │   ├── Button/
│       │   │   │   ├── index.tsx       # Web 默认实现
│       │   │   │   └── index.native.tsx # RN 实现
│       │   │   ├── Card/
│       │   │   └── ...
│       │   └── theme/
│       │       ├── colors.ts      # 共享颜色
│       │       ├── typography.ts  # 共享字体
│       │       └── tokens.ts      # 设计令牌
│       └── package.json
│
├── pnpm-workspace.yaml            # 添加 packages/mobile
└── package.json
```

### 3.2 代码共享策略

#### 3.2.1 类型定义共享

```typescript
// packages/common-all/src/types/analysis.ts
// 已存在，直接复用

export interface TextRangeSelection {
  edition_id: number;
  mode: 'single_chapter' | 'chapter_range' | 'multi_chapter' | 'full_edition';
  chapter_index?: number;
  start_index?: number;
  end_index?: number;
  chapter_indices?: number[];
}

export interface AnalysisTask {
  id: number;
  task_type: string;
  status: 'pending' | 'running' | 'completed' | 'failed';
  progress: number;
  // ...
}
```

#### 3.2.2 API 客户端共享

```typescript
// packages/mobile/src/api/analysis.ts
// 复用 Web 端 API 定义，适配 RN fetch

import { TextRangeSelection, AnalysisTask } from '@saili/common-all';
import { API_BASE_URL } from '../config';

// React Native 的 fetch 无 CORS 限制！
export async function apiCreateAnalysisTask(
  data: TextRangeSelection & { task_type: string }
): Promise<AnalysisTask> {
  const response = await fetch(`${API_BASE_URL}/api/v1/analysis/task/`, {
    method: 'POST',
    headers: { 
      'Content-Type': 'application/json',
      'Authorization': `Bearer ${await getApiKey()}`,
    },
    body: JSON.stringify(data),
  });
  
  if (!response.ok) {
    throw new Error(`Failed: ${response.statusText}`);
  }
  
  return response.json();
}
```

#### 3.2.3 LLM 直接调用（解决 CORS 问题的核心）

```typescript
// packages/mobile/src/services/llm.ts
// React Native 直接调用 LLM API，绕过浏览器 CORS！

import { MMKV } from 'react-native-mmkv';

const storage = new MMKV();

export interface LLMMessage {
  role: 'system' | 'user' | 'assistant';
  content: string;
}

export interface LLMConfig {
  provider: 'moonshot' | 'openai' | 'gemini';
  model: string;
  temperature?: number;
  max_tokens?: number;
  apiKey: string;
}

// 直接调用 Moonshot API（无 CORS！）
async function callMoonshot(
  messages: LLMMessage[],
  config: LLMConfig
): Promise<string> {
  const response = await fetch('https://api.moonshot.cn/v1/chat/completions', {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      'Authorization': `Bearer ${config.apiKey}`,
    },
    body: JSON.stringify({
      model: config.model,
      messages,
      temperature: config.temperature ?? 0.7,
      max_tokens: config.max_tokens ?? 4000,
      stream: false,
    }),
  });

  if (!response.ok) {
    const error = await response.text();
    throw new Error(`Moonshot API error: ${error}`);
  }

  const data = await response.json();
  return data.choices[0].message.content;
}

// 流式调用（打字机效果）
async function* streamMoonshot(
  messages: LLMMessage[],
  config: LLMConfig
): AsyncGenerator<string> {
  const response = await fetch('https://api.moonshot.cn/v1/chat/completions', {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      'Authorization': `Bearer ${config.apiKey}`,
    },
    body: JSON.stringify({
      model: config.model,
      messages,
      stream: true, // 启用流式
    }),
  });

  const reader = response.body?.getReader();
  if (!reader) throw new Error('No response body');

  const decoder = new TextDecoder();
  
  while (true) {
    const { done, value } = await reader.read();
    if (done) break;
    
    const chunk = decoder.decode(value);
    // 解析 SSE 格式的数据
    const lines = chunk.split('\n');
    for (const line of lines) {
      if (line.startsWith('data: ')) {
        const data = line.slice(6);
        if (data === '[DONE]') return;
        
        try {
          const parsed = JSON.parse(data);
          const content = parsed.choices[0]?.delta?.content;
          if (content) yield content;
        } catch {
          // 忽略解析错误
        }
      }
    }
  }
}

export const llmService = {
  async complete(
    messages: LLMMessage[],
    config: LLMConfig
  ): Promise<string> {
    switch (config.provider) {
      case 'moonshot':
        return callMoonshot(messages, config);
      case 'openai':
        return callOpenAI(messages, config);
      case 'gemini':
        return callGemini(messages, config);
      default:
        throw new Error(`Unknown provider: ${config.provider}`);
    }
  },

  stream(
    messages: LLMMessage[],
    config: LLMConfig
  ): AsyncGenerator<string> {
    // 返回异步生成器，UI 层使用 for await...of 消费
    return streamMoonshot(messages, config);
  },
};
```

### 3.3 跨平台组件共享

```typescript
// packages/ui/src/components/Button/index.tsx
// Web 端实现
import React from 'react';

export interface ButtonProps {
  label: string;
  onPress: () => void;
  variant?: 'primary' | 'secondary';
}

export const Button: React.FC<ButtonProps> = ({ label, onPress, variant }) => {
  return (
    <button 
      className={`btn btn-${variant}`}
      onClick={onPress}
    >
      {label}
    </button>
  );
};

// packages/ui/src/components/Button/index.native.tsx
// React Native 实现
import React from 'react';
import { TouchableOpacity, Text, StyleSheet } from 'react-native';
import { ButtonProps } from './types';

export const Button: React.FC<ButtonProps> = ({ label, onPress, variant = 'primary' }) => {
  return (
    <TouchableOpacity 
      style={[styles.button, styles[variant]]}
      onPress={onPress}
    >
      <Text style={styles.text}>{label}</Text>
    </TouchableOpacity>
  );
};

const styles = StyleSheet.create({
  button: {
    paddingHorizontal: 16,
    paddingVertical: 12,
    borderRadius: 8,
  },
  primary: {
    backgroundColor: '#007AFF',
  },
  secondary: {
    backgroundColor: '#6C757D',
  },
  text: {
    color: '#FFF',
    fontSize: 16,
  },
});
```

---

## 4. 核心功能模块

### 4.1 功能优先级

| 模块 | 功能 | 优先级 | 说明 |
|------|------|--------|------|
| **文本阅读** | 章节列表、阅读器、书签 | P0 | 核心基础功能 |
| **LLM 对话** | 直接调用 LLM API 进行分析 | P0 | 解决浏览器限制痛点 |
| **分析任务** | 创建/监控/接收通知 | P1 | 后台处理支持 |
| **人物档案** | 查看/编辑人物信息 | P1 | 数据浏览功能 |
| **设定管理** | 查看/编辑设定 | P1 | 数据浏览功能 |
| **大纲浏览** | 树形大纲展示 | P2 | 辅助功能 |
| **离线同步** | 章节下载/更新 | P2 | 增强体验 |

### 4.2 模块详细设计

#### 4.2.1 文本阅读模块

```typescript
// packages/mobile/src/screens/ReaderScreen.tsx
import React, { useEffect, useState } from 'react';
import { View, ScrollView, Text, StyleSheet } from 'react-native';
import { useRoute } from '@react-navigation/native';
import { WatermelonDB } from '@nozbe/watermelondb';

import { apiGetChapterContent } from '../api/text';
import { useOfflineFirst } from '../hooks/useOfflineFirst';

export const ReaderScreen: React.FC = () => {
  const route = useRoute();
  const { editionId, chapterIndex } = route.params;
  
  // 离线优先：先读本地，再同步远程
  const { data: content, isLoading } = useOfflineFirst({
    localQuery: () => db.chapters.find(chapterId),
    remoteFetch: () => apiGetChapterContent(editionId, chapterIndex),
    onRemoteSuccess: (data) => db.chapters.save(data), // 缓存到本地
  });

  return (
    <ScrollView style={styles.container}>
      <Text style={styles.content}>{content}</Text>
    </ScrollView>
  );
};

// 阅读设置：字体、主题、行间距
const ReaderSettings: React.FC = () => {
  const { settings, updateSettings } = useReaderSettings();
  
  return (
    <View>
      <FontSizeSlider 
        value={settings.fontSize}
        onChange={(size) => updateSettings({ fontSize: size })}
      />
      <ThemeSelector
        value={settings.theme}
        onChange={(theme) => updateSettings({ theme })}
      />
    </View>
  );
};
```

#### 4.2.2 LLM 对话模块（核心亮点）

```typescript
// packages/mobile/src/screens/AnalysisChatScreen.tsx
import React, { useState, useCallback } from 'react';
import { 
  View, FlatList, TextInput, TouchableOpacity, 
  Text, StyleSheet 
} from 'react-native';
import { llmService } from '../services/llm';
import { Markdown } from '../components/Markdown';

interface Message {
  id: string;
  role: 'user' | 'assistant';
  content: string;
  isStreaming?: boolean;
}

export const AnalysisChatScreen: React.FC = () => {
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState('');
  const [isStreaming, setIsStreaming] = useState(false);

  // 发送消息并流式接收响应
  const sendMessage = useCallback(async () => {
    if (!input.trim()) return;

    const userMsg: Message = {
      id: Date.now().toString(),
      role: 'user',
      content: input,
    };

    setMessages(prev => [...prev, userMsg]);
    setInput('');
    setIsStreaming(true);

    // 构建系统提示词（根据 sail_server 的提示词模板）
    const systemPrompt = `你是一个小说文本分析助手，帮助用户分析作品内容。
请根据用户选择的文本范围，提取人物、设定、大纲等信息。`;

    const assistantMsg: Message = {
      id: (Date.now() + 1).toString(),
      role: 'assistant',
      content: '',
      isStreaming: true,
    };

    setMessages(prev => [...prev, assistantMsg]);

    try {
      // 直接调用 LLM，无 CORS 限制！
      const stream = llmService.stream(
        [
          { role: 'system', content: systemPrompt },
          { role: 'user', content: input },
        ],
        {
          provider: 'moonshot',
          model: 'kimi-k2.5',
          apiKey: storage.getString('moonshot_api_key')!,
        }
      );

      // 流式更新 UI（打字机效果）
      for await (const chunk of stream) {
        setMessages(prev => {
          const last = prev[prev.length - 1];
          return [
            ...prev.slice(0, -1),
            { ...last, content: last.content + chunk },
          ];
        });
      }
    } catch (error) {
      console.error('LLM Error:', error);
    } finally {
      setIsStreaming(false);
      setMessages(prev => {
        const last = prev[prev.length - 1];
        return [...prev.slice(0, -1), { ...last, isStreaming: false }];
      });
    }
  }, [input]);

  return (
    <View style={styles.container}>
      <FlatList
        data={messages}
        keyExtractor={item => item.id}
        renderItem={({ item }) => (
          <View style={[
            styles.message,
            item.role === 'user' ? styles.userMsg : styles.assistantMsg
          ]}>
            <Markdown content={item.content} />
            {item.isStreaming && <Text style={styles.cursor}>▊</Text>}
          </View>
        )}
      />
      
      <View style={styles.inputContainer}>
        <TextInput
          style={styles.input}
          value={input}
          onChangeText={setInput}
          placeholder="输入分析请求..."
          multiline
        />
        <TouchableOpacity 
          style={styles.sendButton}
          onPress={sendMessage}
          disabled={isStreaming}
        >
          <Text>发送</Text>
        </TouchableOpacity>
      </View>
    </View>
  );
};
```

#### 4.2.3 后台分析任务模块

```typescript
// packages/mobile/src/tasks/analysisTask.ts
import * as BackgroundFetch from 'expo-background-fetch';
import * as TaskManager from 'expo-task-manager';
import * as Notifications from 'expo-notifications';

const ANALYSIS_TASK = 'background-analysis-task';

// 定义后台任务
TaskManager.defineTask(ANALYSIS_TASK, async () => {
  try {
    // 检查是否有进行中的分析任务
    const pendingTasks = await db.analysisTasks.query(
      Q.where('status', 'running')
    ).fetch();

    for (const task of pendingTasks) {
      // 轮询任务状态
      const remoteStatus = await apiGetTaskProgress(task.remoteId);
      
      if (remoteStatus.progress !== task.progress) {
        await task.updateProgress(remoteStatus.progress);
        
        // 任务完成时发送通知
        if (remoteStatus.status === 'completed') {
          await Notifications.scheduleNotificationAsync({
            content: {
              title: '分析任务完成',
              body: `${task.taskType} 分析已完成，点击查看结果`,
            },
            trigger: null, // 立即发送
          });
        }
      }
    }

    return BackgroundFetch.BackgroundFetchResult.NewData;
  } catch (error) {
    console.error('Background task error:', error);
    return BackgroundFetch.BackgroundFetchResult.Failed;
  }
});

// 注册后台任务
export async function registerAnalysisTask(): Promise<void> {
  const isRegistered = await TaskManager.isTaskRegisteredAsync(ANALYSIS_TASK);
  
  if (!isRegistered) {
    await BackgroundFetch.registerTaskAsync(ANALYSIS_TASK, {
      minimumInterval: 60, // 每 60 秒检查一次
      stopOnTerminate: false, // App 关闭后继续运行
      startOnBoot: true, // 设备重启后自动启动
    });
  }
}

// 任务监控界面
export const TaskMonitorScreen: React.FC = () => {
  const tasks = useQuery(db.analysisTasks);

  return (
    <FlatList
      data={tasks}
      renderItem={({ item }) => (
        <View style={styles.taskItem}>
          <Text>{item.taskType}</Text>
          <ProgressBar progress={item.progress} />
          <Text>{item.status}</Text>
        </View>
      )}
    />
  );
};
```

---

## 5. 离线优先架构

### 5.1 数据同步策略

```typescript
// packages/mobile/src/hooks/useOfflineFirst.ts
import { useEffect, useState } from 'react';
import NetInfo from '@react-native-community/netinfo';

interface UseOfflineFirstOptions<T> {
  localQuery: () => Promise<T | null>;
  remoteFetch: () => Promise<T>;
  onRemoteSuccess: (data: T) => Promise<void>;
}

export function useOfflineFirst<T>({
  localQuery,
  remoteFetch,
  onRemoteSuccess,
}: UseOfflineFirstOptions<T>) {
  const [data, setData] = useState<T | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<Error | null>(null);

  useEffect(() => {
    let isMounted = true;

    async function load() {
      try {
        // 1. 先尝试从本地获取
        const localData = await localQuery();
        
        if (localData && isMounted) {
          setData(localData);
          setIsLoading(false);
        }

        // 2. 检查网络状态
        const netInfo = await NetInfo.fetch();
        
        if (netInfo.isConnected) {
          // 3. 有网络时获取远程数据
          const remoteData = await remoteFetch();
          
          if (isMounted) {
            setData(remoteData);
            // 4. 更新本地缓存
            await onRemoteSuccess(remoteData);
          }
        }
      } catch (err) {
        if (isMounted) {
          setError(err instanceof Error ? err : new Error(String(err)));
        }
      } finally {
        if (isMounted) {
          setIsLoading(false);
        }
      }
    }

    load();

    return () => {
      isMounted = false;
    };
  }, []);

  return { data, isLoading, error };
}
```

### 5.2 数据库 Schema (WatermelonDB)

```typescript
// packages/mobile/src/db/schema.ts
import { appSchema, tableSchema } from '@nozbe/watermelondb';

export default appSchema({
  version: 1,
  tables: [
    // 章节缓存
    tableSchema({
      name: 'chapters',
      columns: [
        { name: 'remote_id', type: 'string', isIndexed: true },
        { name: 'edition_id', type: 'number', isIndexed: true },
        { name: 'index', type: 'number' },
        { name: 'title', type: 'string' },
        { name: 'content', type: 'string' },
        { name: 'sync_status', type: 'string' }, // synced, pending, error
        { name: 'updated_at', type: 'number' },
      ],
    }),
    
    // 阅读进度
    tableSchema({
      name: 'reading_progress',
      columns: [
        { name: 'edition_id', type: 'number', isIndexed: true },
        { name: 'chapter_index', type: 'number' },
        { name: 'position', type: 'number' },
        { name: 'updated_at', type: 'number' },
      ],
    }),
    
    // 分析任务（本地缓存）
    tableSchema({
      name: 'analysis_tasks',
      columns: [
        { name: 'remote_id', type: 'string', isIndexed: true },
        { name: 'task_type', type: 'string' },
        { name: 'status', type: 'string' },
        { name: 'progress', type: 'number' },
        { name: 'result', type: 'string', isOptional: true },
        { name: 'created_at', type: 'number' },
      ],
    }),
  ],
});
```

---

## 6. 项目配置

### 6.1 Expo 配置

```json
// packages/mobile/app.json
{
  "expo": {
    "name": "SailZen",
    "slug": "sailzen",
    "version": "1.0.0",
    "orientation": "portrait",
    "icon": "./assets/icon.png",
    "userInterfaceStyle": "automatic",
    "splash": {
      "image": "./assets/splash.png",
      "resizeMode": "contain",
      "backgroundColor": "#ffffff"
    },
    "assetBundlePatterns": ["**/*"],
    "ios": {
      "supportsTablet": true,
      "bundleIdentifier": "com.sailzen.mobile"
    },
    "android": {
      "adaptiveIcon": {
        "foregroundImage": "./assets/adaptive-icon.png",
        "backgroundColor": "#ffffff"
      },
      "package": "com.sailzen.mobile"
    },
    "web": {
      "favicon": "./assets/favicon.png"
    },
    "plugins": [
      "expo-background-fetch",
      "expo-notifications",
      [
        "expo-build-properties",
        {
          "ios": {
            "newArchEnabled": true
          },
          "android": {
            "newArchEnabled": true
          }
        }
      ]
    ]
  }
}
```

### 6.2 EAS Build 配置

```json
// packages/mobile/eas.json
{
  "cli": {
    "version": ">= 7.0.0"
  },
  "build": {
    "development": {
      "developmentClient": true,
      "distribution": "internal"
    },
    "preview": {
      "distribution": "internal",
      "android": {
        "buildType": "apk"
      }
    },
    "production": {
      "autoIncrement": true
    }
  },
  "submit": {
    "production": {}
  }
}
```

### 6.3 依赖配置

```json
// packages/mobile/package.json
{
  "name": "@saili/mobile",
  "version": "1.0.0",
  "main": "expo/AppEntry.js",
  "scripts": {
    "start": "expo start",
    "android": "expo run:android",
    "ios": "expo run:ios",
    "build:android": "eas build -p android",
    "build:ios": "eas build -p ios"
  },
  "dependencies": {
    "expo": "~50.0.0",
    "expo-background-fetch": "~11.8.0",
    "expo-notifications": "~0.27.0",
    "expo-file-system": "~16.0.0",
    "react": "18.2.0",
    "react-native": "0.73.0",
    "react-navigation": "^7.0.0",
    "@react-navigation/native": "^7.0.0",
    "@react-navigation/bottom-tabs": "^7.0.0",
    "@react-navigation/stack": "^7.0.0",
    "zustand": "^4.4.0",
    "axios": "^1.6.0",
    "react-native-mmkv": "^2.11.0",
    "@nozbe/watermelondb": "^0.27.0",
    "@react-native-community/netinfo": "^11.2.0",
    "react-native-markdown-display": "^7.0.0",
    "@saili/common-all": "workspace:*",
    "@saili/ui": "workspace:*"
  },
  "devDependencies": {
    "@types/react": "~18.2.45",
    "typescript": "^5.3.0"
  }
}
```

---

## 7. 实现路线图

### Phase 1: 项目初始化与基础架构 (3-4 周)

- [ ] 初始化 Expo 项目 (Managed Workflow)
- [ ] 配置 pnpm workspace，集成到 monorepo
- [ ] 配置 TypeScript、ESLint、Prettier
- [ ] 设置 WatermelonDB 本地数据库
- [ ] 配置 React Navigation 路由框架
- [ ] 实现 Zustand store 共享架构
- [ ] 复用 @saili/common-all 类型定义

### Phase 2: 核心功能 - 阅读与 LLM (4-5 周)

- [ ] 作品/章节列表页（复用 Web API 层）
- [ ] 离线优先阅读器（竖向滚动）
- [ ] 阅读设置（字体、主题、行间距）
- [ ] **LLM 直接调用服务**（核心亮点）
- [ ] 对话式分析界面（流式响应）
- [ ] API Key 配置管理

### Phase 3: 分析任务与后台处理 (3-4 周)

- [ ] 分析任务创建（复用 Web 端逻辑）
- [ ] 后台任务注册（expo-background-fetch）
- [ ] 任务进度轮询与本地缓存
- [ ] 推送通知（expo-notifications）
- [ ] 任务历史记录

### Phase 4: 数据浏览与同步 (3 周)

- [ ] 人物档案浏览
- [ ] 设定管理浏览
- [ ] 大纲树形展示
- [ ] 阅读进度同步
- [ ] 章节内容离线缓存

### Phase 5: 优化与发布 (2-3 周)

- [ ] 性能优化（FlatList、图片懒加载）
- [ ] 错误处理与重试机制
- [ ] EAS Build 配置与测试
- [ ] Android APK 发布
- [ ] 文档编写

**总计: 15-19 周**

---

## 8. 解决核心痛点的方案

### 8.1 LLM 调用无 CORS 限制

```
Web 端 (packages/site):
  浏览器 ──CORS 限制──❌──► Moonshot API
                     
React Native (packages/mobile):
  App ──直接 fetch──✅──► Moonshot API
       (无 CORS 限制)
```

### 8.2 后台任务支持

```
Web 端:
  页面关闭 ──► 分析任务中断

React Native:
  App 后台 ──► Background Fetch 继续轮询
  App 关闭 ──► 推送通知告知任务完成
```

### 8.3 代码复用最大化

| 复用内容 | 复用率 | 实现方式 |
|----------|--------|----------|
| TypeScript 类型 | 100% | `@saili/common-all` |
| API 端点定义 | 90% | 复用接口，替换 fetch 实现 |
| 业务逻辑 Hooks | 70% | 抽取平台无关逻辑到 `@saili/hooks` |
| UI 组件 | 50% | `@saili/ui` + 平台适配文件 |
| 样式/主题 | 80% | 共享 design tokens |

---

## 9. 与现有系统集成

### 9.1 后端 API 兼容

sail_server 无需修改，React Native 直接使用现有 `/api/v1/*` 接口。

### 9.2 Web 端与移动端共存

```
┌─────────────────┐         ┌─────────────────┐
│   packages/site │         │ packages/mobile │
│   (Web 端)       │         │   (React Native)│
├─────────────────┤         ├─────────────────┤
│ React + Vite    │         │ React Native    │
│ 浏览器限制       │         │ 直接 LLM 调用   │
│ 依赖在线        │         │ 离线优先        │
└────────┬────────┘         └────────┬────────┘
         │                           │
         └───────────┬───────────────┘
                     │
                     ▼
            ┌─────────────────┐
            │   sail_server   │
            │   (Litestar)    │
            └─────────────────┘
```

### 9.3 数据同步

- **阅读进度**: 两端通过后端 API 同步
- **分析任务**: 任务状态实时同步
- **分析结果**: 统一存储于后端
- **离线内容**: 移动端本地缓存

---

## 10. 风险评估与应对

| 风险 | 可能性 | 影响 | 应对措施 |
|------|--------|------|----------|
| Expo 生态限制 | 中 | 中 | 预留 Eject 方案，评估 Bare Workflow |
| LLM 流式响应稳定性 | 中 | 中 | 实现重试机制，降级为非流式 |
| 后台任务被系统限制 | 高 | 中 | 使用 expo-background-fetch，遵守系统限制 |
| 数据同步冲突 | 中 | 中 | 时间戳策略，用户确认机制 |
| 大型文本渲染性能 | 中 | 高 | 使用 FlashList，虚拟化长列表 |

---

## 11. 附录

### 11.1 参考资源

- [Expo 官方文档](https://docs.expo.dev/)
- [React Navigation 文档](https://reactnavigation.org/)
- [WatermelonDB 文档](https://watermelondb.dev/)
- [React Native New Architecture](https://reactnative.dev/docs/new-architecture-intro)

### 11.2 相关文档

- [文本分析系统设计](./text-analysis-system.md)
- [后端 API 文档](../site/doc/)
- [LLM 配置指南](../../sail_server/utils/llm/available_providers.py)

---

*文档结束*
