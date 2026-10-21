# Lazulite Studio 注音词典

独立构建四个可直接导入 Studio 的固定读音 ZIP：

| ID | 内容 | 评分 |
| --- | --- | --- |
| zh-pinyin | 汉语拼音，带调符号；简繁查询词形 | jieba 词频增强 |
| yue-jyutping | 粤语粤拼，数字调号；简体查询别名 | essay-cantonese 权重增强 |
| teochew-chaozhou-puj | 潮州府城，PUJ 白话字 | 基础成本 |
| teochew-shantou-puj | 汕头市区，PUJ 白话字 | 基础成本 |

在 Studio「注音词典」中选择 Release 的 ZIP，核对名称、地区、版本和来源后安装。同 ID 的包可以显式替换，含同版本修改包和旧版本包。格式 v1 也接受自行制作的词典。词典提供固定读音；缺词、并列读音及语言语境仍需人工处理。

## 独立构建

需要 Python 3.12、网络连接和约 3 GiB 可用内存。源码和生成数据均可在本机编辑。无需安装 Studio、输入法或额外的口音运行时。

```sh
python -m venv .venv
# Linux/macOS:
source .venv/bin/activate
# Windows PowerShell: .venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
python -m dictbuilder fetch
python -m pytest -q tests/test_contract.py
python -m dictbuilder build --all
python -m dictbuilder validate
python -m pytest -q tests/test_full_build.py
python -m dictbuilder report
```

`sources.json` 固定来源提交、选用文件、解析规则版本和许可；pujbase 的字词语料子模块提交单独记录。下载位于 `.cache/<source>/<commit>/`。修改该副本可直接重新构建；删除对应缓存目录会重新取得选定的上游快照。构建不会自动更新来源版本。OpenCC 的 s2t/t2s 配置和依赖版本固定在包配置与 requirements 中。

`dist/` 仅在四个包全部转换及校验通过后替换。ZIP 内文件排序、JSON 编码及 ZIP 元数据固定；运行耗时等易变值位于 `reports/`。`reports/build.json` 记录展开后的输入候选数、输出/重复/排除闭合、原始及别名词形、词频关联、细粗对应及体积；逐项排除和别名冲突分别输出 JSONL。`input` 的计数单位是展开后的文字—读音候选，不把多个口音或简繁写法当作独立上游原始记录。

## 数据规则

- 普通话读取 `pinyin.txt` 和 `large_pinyin.txt`，不再叠加聚合文件的组成子表。只有明确的 `kMandarin_8105.txt` 常用音表提供字音优先级。
- 粤拼读取 chars/words 的 Rime 列定义；百分比相对 essay 基础权重解释，用于同词候选偏好。`0%` 保留。无 code 或不能解释为完整粤拼音节的记录有原因地排除。
- 两种潮州话读取同一 entries/phrases/accents 与 pujcorpora 标准语料；执行静态口音规则，地区覆盖直接使用地区音。词组保持整组对应；保留可确定的音节及原始连字符、空格和轻声标记，分隔符附着于实际音节。常用/罕用用于候选偏好，不当作词频；不执行连续变调。
- 原文字精确关联频率优先；别名关联仅接受无冲突关系。缺失或非正频率质量为 1。去重原始词形质量与一个未命中质量归一化后生成 `round(-log(p)*1000000)`。
- 别名不增加概率质量。原生词形成本优先；多个来源落入同一生成别名且成本冲突时保留较高成本并报告。不同读音/对应关系保留为候选。
- 字形转换只有在分段转换与整词转换一致时保留细边界，否则保留整组对应。空白和格式约定的句读边界不跨越。

## 发布

`Prepare or publish dictionaries` 手动工作流提供两个操作：

1. `prepare-draft`：指定合法 Git tag，例如 `v0.1.0`、`0.1.0` 或 `preview-2026-10-21`；已有 tag 使用其对应提交，否则固定到所选分支当前提交。实际全量构建四包，上传草稿 Release 和独立诊断工件。
2. `publish-reviewed-draft`：确认实际草稿产物后手动选择；检查必需资产齐全后公开同一草稿。

Release tag 与词典内容版本独立。`packages.json.version` 决定包内版本及 ZIP 文件名；指定另一 tag 不会改写词典内容版本。Studio 的默认下载来源由其 `packaging/dictionaries.json` 单独选择，需要填写实际公开的 Release tag。

完整格式检查在每个包构建完成后执行一次。测试、内部工件传递、上传及公开步骤复用该构建结果，只检查交接所需文件是否存在；草稿可包含额外说明附件，重跑只替换必需词典资产。`validate` 命令供独立检查外部包或手工修改后的包使用；Studio 导入时执行自己的外部数据边界校验。

同一标签的重跑只能更新同一提交的草稿；公开版本不能覆盖。构建作业只读，只有 Release 作业使用仓库 GITHUB_TOKEN 写权限。不需个人令牌。普通 push/PR 仅执行契约验证；手动发布不由 push 触发。

## 格式与许可

格式见 [FORMAT.md](FORMAT.md)。源代码采用 [AGPL-3.0](LICENSE)。数据按各来源许可分开归属，见 [署名与变更说明](licenses/ATTRIBUTION.txt)、`sources.json` 及每个包的 `licenses/`。第三方库由构建环境安装，数据包只携带声明与固定文本数据。
