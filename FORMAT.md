# 固定读音词典格式 v1

每包为 UTF-8 普通 ZIP，含 `manifest.json`、`entries.jsonl`、`sources.json` 和 `licenses/`。路径不能越界、重复、为符号链接或包含可执行入口。读取者执行必要结构校验，允许内容修改，不校验发行内容摘要、历史计数或发布者白名单。

manifest 必需字段：

```json
{"formatVersion":1,"id":"my-dictionary","version":"1","name":"我的词典","language":"zh","region":"普通话","notation":"带调拼音","readingPolicy":"fixed","entries":"entries.jsonl","scoring":{"mode":"uniform"}}
```

ID 为 1–80 个小写字母、数字、`.`、`_`、`-`，首位为字母或数字。名称、版本、语言、地区、拼写说明为非空字符串。`entryCount` 和来源摘要可以作为说明，实际条数由读取者统计。`sources.json` 是来源对象或列表，`licenses/` 至少含一个署名或许可文件。

每个不同 surface 一行，候选放在同一词条：

```json
{"surface":"重庆","candidates":[{"id":"r1","priority":0,"segments":[{"base":"重","annotate":true,"units":["chóng"]},{"base":"庆","annotate":true,"units":["qìng"]}]}]}
```

`priority` 是整数，越大越优先，仅比较同 surface 内的读音。没有来源依据时相等。同候选各段的 base 连续拼接必须等于 surface，不能切断字素。`annotate:true` 配非空 units，单元为不为空的完整文本；`annotate:false` 配空 units，表示已知但无需注音。仅整词对应的资料可有一个多字 base 和多个 units；音节数不证明逐字对应。

`scoring.mode=uniform`：所有词条省略 cost，每条命中边和每个未命中字素成本均为 1。

`scoring.mode=weighted`：manifest 带正整数 `unknownCost`，每个词条带非负整数 `cost`。整数范围不超过 JavaScript 安全整数。两种模式均先最小化总代价，同分再最小化未命中字素；仍同分且结果不同的最小连续范围报告歧义。不能使用文件行序默选。

查询在 Unicode 码点序列上进行；合法端点必须是扩展字素边界。硬边界是 Unicode 空白以及下列明确句读：

```text
,，、.。!！?？:：;；()（）[]［］{}｛｝「」『』【】〈〉《》“”"…⋯
```

词条不能跨硬边界。连字符与撇号不在该集合。读音里的空格、连字符、调号和组合字符属于该单元文本，读取者不重新分音节。

资源边界：ZIP 最多 256 个成员、总解压 512 MiB；每条 JSONL 最多 1 MiB、最多 200 万个不同词形；surface 最多 1024 码点，每条最多 1024 候选/对应段，每段最多 1024 单元，每单元最多 4096 码点。校验失败的包不能替换现用实例。内容版本与本地安装实例标识分开；重装同版本也产生新实例。

Studio 的 HTTP 范围使用码点偏移，前端在接口边界转换为 UTF-16。范围状态为 known、unknown、ambiguous、boundary 或 unannotated；未知/歧义由响应表达，不是词条数据。保存的项目仅保留最终正文、读音单元和时间，独立于词典安装状态。

## 构建执行说明

### 环境要求

需要 Python 3.12、网络连接和约 3 GiB 可用内存。源码和生成数据均可在本机编辑。无需安装 Studio、输入法或额外的口音运行时。

### 来源与缓存

`sources.json` 固定来源提交、选用文件、解析规则版本和许可；pujbase 的字词语料子模块提交单独记录。下载位于 `.cache/<source>/<commit>/`。修改该副本可直接重新构建；删除对应缓存目录会重新取得选定的上游快照。构建不会自动更新来源版本。OpenCC 的 s2t/t2s 配置和依赖版本固定在包配置与 requirements 中。

### 产物与诊断

`dist/` 仅在全部配置包转换及校验通过后替换。ZIP 内文件排序、JSON 编码及 ZIP 元数据固定；运行耗时等易变值位于 `reports/`。`reports/build.json` 记录展开后的输入候选数、输出/重复/排除闭合、原始及别名词形、词频关联、细粗对应及体积；逐项排除和别名冲突分别输出 JSONL。`input` 的计数单位是展开后的文字—读音候选，不把多个口音或简繁写法当作独立上游原始记录。
