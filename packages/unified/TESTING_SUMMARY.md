# Unified 模块测试框架搭建总结

## 完成的工作

### 1. 完善测试配置 ✅

- **更新 `package.json`**：添加了 `test:watch` 和 `test:coverage` 脚本，参考 `common-server` 模块
- **Jest 配置**：已有 `jest.config.mjs`，配置了 ESM 支持和覆盖率收集

### 2. 创建测试基础设施 ✅

#### Fixtures (`src/__tests__/fixtures/testNotes.ts`)
- `createTestVault()` - 创建测试 vault
- `createTestConfig()` - 创建测试配置
- `createTestNote()` - 创建基本测试 note
- `createTestNoteWithBody()` - 创建带内容的 note
- `createTestNoteWithWikiLinks()` - 创建带 wiki links 的 note
- `createTestNoteWithHashtags()` - 创建带 hashtags 的 note
- `createTestNoteWithFrontmatter()` - 创建带 frontmatter 的 note

#### 测试工具 (`src/__tests__/utils/testHelpers.ts`)
- `createTestProcessor()` - 创建基础 remark processor
- `processMarkdownToAST()` - 处理 markdown 到 AST
- `processMarkdownToString()` - 处理 markdown 到字符串
- `createFullTestProcessor()` - 创建完整 Dendron processor
- `processNoteFull()` - 使用完整 processor 处理 note
- 字符串和正则匹配断言辅助函数

### 3. 编写的测试案例 ✅

#### Remark 插件测试
- ✅ `src/remark/__tests__/wikiLinks.test.ts` - Wiki links 插件测试
  - LINK_REGEX 和 LINK_REGEX_LOOSE 测试
  - matchWikiLink 函数测试
  - 插件集成测试
  - 完整处理流程测试

- ✅ `src/remark/__tests__/hashtag.test.ts` - Hashtag 插件测试
  - HASHTAG_REGEX 和 HASHTAG_REGEX_LOOSE 测试
  - HashTagUtils 工具函数测试
  - 插件集成测试
  - 完整处理流程测试

- ✅ `src/remark/__tests__/zdocTags.test.ts` - ZDoc tags 插件测试
  - ZDOCTAG_REGEX 测试
  - ZDocTagUtils 工具函数测试
  - 插件集成测试

- ✅ `src/remark/__tests__/blockAnchors.test.ts` - Block anchors 插件测试
  - 插件集成测试
  - 完整处理流程测试

#### Rehype 插件测试
- ✅ `src/rehype/__tests__/wrap.test.ts` - Wrap 插件测试
  - 元素包装测试
  - 选择器匹配测试
  - 复杂包装器测试

#### 工具函数测试
- ✅ `src/__tests__/utils.test.ts` - MdastUtils 测试
  - genMDMsg 和 genMDErrorMsg 测试
  - findIndex 测试
  - findHeader 测试
  - renderFromNote 测试

- ✅ `src/__tests__/utilsWeb.test.ts` - MDUtilsV5Web 测试
  - procRehypeWeb 创建和运行测试
  - 各种 markdown 元素处理测试

### 4. 文档撰写 ✅

- ✅ `README_TESTING.md` - 完整的测试框架文档
  - 概述和目录结构
  - 测试框架配置说明
  - 测试工具和 Fixtures 使用指南
  - 编写测试的最佳实践
  - 运行测试和覆盖率指南
  - 维护指南和常见问题

## 测试文件结构

```
packages/unified/
├── src/
│   ├── __tests__/
│   │   ├── fixtures/
│   │   │   └── testNotes.ts          # 测试数据 fixtures
│   │   ├── utils/
│   │   │   └── testHelpers.ts        # 测试辅助函数
│   │   ├── utils.test.ts            # utils.ts 测试
│   │   └── utilsWeb.test.ts         # utilsWeb.ts 测试
│   ├── remark/
│   │   ├── __tests__/
│   │   │   ├── wikiLinks.test.ts    # Wiki links 测试
│   │   │   ├── hashtag.test.ts      # Hashtag 测试
│   │   │   ├── zdocTags.test.ts     # ZDoc tags 测试
│   │   │   └── blockAnchors.test.ts # Block anchors 测试
│   │   └── ...
│   ├── rehype/
│   │   ├── __tests__/
│   │   │   └── wrap.test.ts         # Wrap 插件测试
│   │   └── ...
│   └── ...
├── jest.config.mjs                  # Jest 配置
├── package.json                    # 包含测试脚本
├── README_TESTING.md               # 测试框架文档
└── TESTING_SUMMARY.md              # 本文档
```

## 测试覆盖范围

### 已覆盖
- ✅ Wiki links 解析和渲染
- ✅ Hashtags 解析和渲染
- ✅ ZDoc tags 解析
- ✅ Block anchors 解析
- ✅ Rehype wrap 插件
- ✅ MdastUtils 工具函数
- ✅ MDUtilsV5Web 处理器

### 待扩展（建议）
- [ ] 更多 remark 插件测试（extendedImage, noteRefsV2, hierarchies 等）
- [ ] decorations 模块测试
- [ ] SiteUtils 测试
- [ ] utilsv5 完整测试
- [ ] 边界情况和错误处理测试
- [ ] 性能测试

## 使用方法

### 运行测试

```bash
# 运行所有测试
pnpm test

# 监视模式
pnpm test:watch

# 生成覆盖率报告
pnpm test:coverage
```

### 编写新测试

参考 `README_TESTING.md` 中的详细指南，或查看现有测试文件作为示例。

## 注意事项

1. **依赖问题**：如果遇到模块缺失错误，可能需要运行 `pnpm install` 安装依赖
2. **ESM 支持**：测试框架配置为 ESM 模式，确保导入语句使用正确的语法
3. **覆盖率阈值**：当前设置为 10%，建议随着测试增加逐步提高

## 后续建议

1. **持续集成**：在 CI/CD 流程中集成测试运行
2. **覆盖率提升**：逐步提高覆盖率阈值到 60-80%
3. **测试维护**：遵循测试最佳实践，保持测试代码质量
4. **文档更新**：随着功能增加，及时更新测试文档

## 参考

- 测试框架文档：`README_TESTING.md`
- Jest 文档：https://jestjs.io/
- Unified 文档：https://unifiedjs.com/
