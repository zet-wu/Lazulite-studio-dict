# 数据来源与转换说明

词典构建将上游字音、词组和口音规则转换为 Studio 可直接读取的固定读音数据。来源提交、选用文件与解析规则版本记录在 [sources.json](sources.json)，各包使用的来源及口音记录在 [packages.json](packages.json)。包内结构见 [FORMAT.md](FORMAT.md)。

## 普通话拼音

单字读音来自 [pinyin-data](https://github.com/mozillazg/pinyin-data) 的 `pinyin.txt`，词组读音来自 [phrase-pinyin-data](https://github.com/mozillazg/phrase-pinyin-data) 的 `large_pinyin.txt`。构建直接读取这两个文件，避免重复叠加聚合词表的组成子表。词频使用 [jieba](https://github.com/fxsjy/jieba) 的 `jieba/dict.txt`。

单字候选的优先级由 `kMandarin_8105.txt` 中明确标注的常用音决定。读取时先将拼音统一为 Unicode NFC，再分解字母和声调组合进行识别；含 `?`、`->` 或 `<-` 标记的记录不参与常用音选择。其他候选仍保留在词典中。

普通话包通过 OpenCC 的 `s2t`、`t2s` 转换生成简繁查询词形。这样，同一条读音可以通过相应的简体或繁体写法查询。

## 粤语粤拼

读音和词频来自 [rime-cantonese](https://github.com/rime/rime-cantonese)。构建按 Rime 文件头声明的列读取 `jyut6ping3.chars.dict.yaml` 和 `jyut6ping3.words.dict.yaml`，以 `essay-cantonese.txt` 提供基础词频。

候选权重中的百分比按该词的基础词频换算，用于同一词形内的读音优先级；`0%` 作为有效值保留。没有读音代码，或代码无法解析为完整粤拼音节的记录，会被排除并写入诊断报告。粤拼包使用 OpenCC 的 `t2s` 生成简体查询别名。

## 潮州话八种口音

八个口音包共用 [pujbase](https://github.com/pujdict/pujbase) 的字音、词组与口音规则，以及 [pujcorpora](https://github.com/pujdict/pujcorpora) 的标准语料。主要输入为 `entries.yml`、`phrases.yml`、`accents.yml`、`fuzzy_rules.yml` 和 `std/**/*.std.yml`。

| 包 ID | 来源采音点 | 来源口音标识 |
| --- | --- | --- |
| teochew-chaozhou-puj | 潮州府城 | `ChaoZhou_FuCheng` |
| teochew-raoping-puj | 饶平黄冈 | `RaoPing_HuangGang` |
| teochew-chenghai-puj | 澄海澄城 | `ChengHai_ChengCheng` |
| teochew-shantou-puj | 汕头市区 | `ShanTou_ShiQu` |
| teochew-jieyang-puj | 揭阳榕城 | `JieYang_RongCheng` |
| teochew-puning-puj | 普宁流沙 | `PuNing_LiuSha` |
| teochew-chaoyang-puj | 潮阳和平 | `ChaoYang_HePing` |
| teochew-huilai-puj | 惠来惠城 | `HuiLai_HuiCheng` |

构建时将基础读音按所选采音点的静态规则转换为 PUJ 白话字。来源中已经明确给出的地区读音直接采用，避免重复转换。常用、罕用标记用于候选读音的优先级；这类标记不作为词频使用，八包采用统一基础成本。

词组保留可确定的音节、连字符、空格和轻声标记，分隔符附着于实际音节。包内保存固定读音，不计算连续变调，也不维护额外的逐词补音、纠音或调频表。

## 词频与查询别名

普通话和粤拼使用词频生成词条成本。先按原始词形精确查找频率；精确查询未命中时，只有归属无冲突、可确定唯一频率的别名关联才参与计算。缺失或非正频率统一取质量 1。

对去重后的原始词形计算概率时，分母为所有词形质量之和再加 1；额外的 1 表示未命中项。词条成本为 `round(-log(p) * 1000000)`，其中 `p` 是该词形质量占上述总量的比例。频率越高，成本越低。

简繁别名共享原始词条的读音和成本，不额外增加概率质量。别名与原生词形重合时，以原生词形成本为准；多个来源生成同一别名且成本不同，则保留较高成本，并记录冲突。不同读音或不同正文对应关系仍保留为独立候选。

## 正文与读音的对应

构建按完整字素处理正文，组合字符作为一个整体。正文的字素数与现成读音单元数相等时，逐字分配读音；数量不等时保留原段对应。连字符和轻声标记继续附着在原读音单元上。

生成简繁别名时，如果逐段字形转换与整词转换结果一致，就保留原分段；否则先采用整组正文与读音对应，再按上述等长规则细分。最终按对应结构去重，重复候选保留最高优先级。词条不跨越空白和格式约定的句读边界，具体边界见 [FORMAT.md](FORMAT.md)。

## 来源版本、诊断与许可

构建使用 `sources.json` 固定的上游快照；pujcorpora 的子模块提交单独记录。各包携带选用来源的信息、许可和署名，便于追溯。转换代码的许可与数据来源许可分别适用，详见[署名与变更说明](licenses/ATTRIBUTION.txt)。

`reports/build.json` 汇总转换数量、别名关联和产物体积，逐项排除及别名冲突另存为 JSONL。报告中的 `input` 表示展开后的“文字—读音候选”数量；同一来源产生多个口音或简繁写法时，不将它们解释为多条独立的上游原始记录。
