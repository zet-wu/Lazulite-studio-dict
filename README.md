# Lazulite Studio 注音词典

本仓库是 [Lazulite Studio](https://github.com/zet-wu/Lazulite-studio) 中的“词典注音”功能所使用的词典的仓库，目前提供普通话拼音、粤语粤拼、潮州话（八个地区口音包）三种方言的词典。从 Release 页下载的 zip 包可直接导入 Lazulite Studio，同 ID 的包可以显式替换。也可参考本仓库的词典结构，制作自己需要的词典。

词典列表：

| ID | 内容及来源 |
| --- | --- |
| zh-pinyin | 汉语拼音，带调符号；简繁查询词形。读音来自 [pinyin-data](https://github.com/mozillazg/pinyin-data) 和 [phrase-pinyin-data](https://github.com/mozillazg/phrase-pinyin-data)，词频来自 [jieba](https://github.com/fxsjy/jieba)。 |
| yue-jyutping | 粤语粤拼，数字调号；简体查询别名。读音及词频来自 [rime-cantonese](https://github.com/rime/rime-cantonese)。 |
| teochew-chaozhou-puj | 潮州话·潮州，PUJ 白话字。字音及口音规则来自 [pujbase](https://github.com/pujdict/pujbase)，语料来自 [pujcorpora](https://github.com/pujdict/pujcorpora)。 |
| teochew-raoping-puj | 潮州话·饶平，PUJ 白话字。字音及口音规则来自 [pujbase](https://github.com/pujdict/pujbase)，语料来自 [pujcorpora](https://github.com/pujdict/pujcorpora)。 |
| teochew-chenghai-puj | 潮州话·澄海，PUJ 白话字。字音及口音规则来自 [pujbase](https://github.com/pujdict/pujbase)，语料来自 [pujcorpora](https://github.com/pujdict/pujcorpora)。 |
| teochew-shantou-puj | 潮州话·汕头，PUJ 白话字。字音及口音规则来自 [pujbase](https://github.com/pujdict/pujbase)，语料来自 [pujcorpora](https://github.com/pujdict/pujcorpora)。 |
| teochew-jieyang-puj | 潮州话·揭阳，PUJ 白话字。字音及口音规则来自 [pujbase](https://github.com/pujdict/pujbase)，语料来自 [pujcorpora](https://github.com/pujdict/pujcorpora)。 |
| teochew-puning-puj | 潮州话·普宁，PUJ 白话字。字音及口音规则来自 [pujbase](https://github.com/pujdict/pujbase)，语料来自 [pujcorpora](https://github.com/pujdict/pujcorpora)。 |
| teochew-chaoyang-puj | 潮州话·潮阳，PUJ 白话字。字音及口音规则来自 [pujbase](https://github.com/pujdict/pujbase)，语料来自 [pujcorpora](https://github.com/pujdict/pujcorpora)。 |
| teochew-huilai-puj | 潮州话·惠来，PUJ 白话字。字音及口音规则来自 [pujbase](https://github.com/pujdict/pujbase)，语料来自 [pujcorpora](https://github.com/pujdict/pujcorpora)。 |

潮州话八个地区口音包的具体来源为：

| ID | 来源采音点 |
| --- | --- |
| teochew-chaozhou-puj | 潮州府城 |
| teochew-raoping-puj | 饶平黄冈 |
| teochew-chenghai-puj | 澄海澄城 |
| teochew-shantou-puj | 汕头市区 |
| teochew-jieyang-puj | 揭阳榕城 |
| teochew-puning-puj | 普宁流沙 |
| teochew-chaoyang-puj | 潮阳和平 |
| teochew-huilai-puj | 惠来惠城 |

## 独立构建

需要 Python 3.12、网络连接和约 3 GiB 可用内存。

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

## 格式与许可

格式见 [FORMAT.md](FORMAT.md)。源代码采用 [AGPL-3.0](LICENSE)。数据按各来源许可分开归属，见 [署名与变更说明](licenses/ATTRIBUTION.txt)、`sources.json` 及每个包的 `licenses/`。。
