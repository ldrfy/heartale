# Heartale Project Notes

## Python

- 默认避免常见 `pylint` 问题，优先通过拆函数、收参数对象、提公共逻辑解决问题，不优先加 `# pylint: disable`。
- 新增或修改 Python 函数时，默认补中文 docstring。
- docstring 风格固定为：函数简述、空行、`Args:`、有返回值时再写 `Returns:`。
- `Args:` 和 `Returns:` 的说明使用简洁中文，不保留 `_type_`、`_description_` 之类占位内容。
- 如果函数没有返回值，不写 `Returns:`。
- 类定义使用 `class Foo:`，模块顶部使用标准模块 docstring。

## 结构

- 纯逻辑、GUI 与 CLI 共用、且不依赖 GTK 的代码放在 `src/utils`。
- `src/pages` 只放页面逻辑或紧耦合页面状态的 mixin。
- `src/widgets` 只放可复用 GTK 组件，不放依赖某个页面内部状态的大段逻辑。
- 涉及 GTK 的代码不要放进 CLI 会导入的公共模块，避免终端环境因缺少 `gi` 失败。

## TTS

- `src/tts` 根目录放公共能力；具体后端放在 `src/tts/backends`。
- 单个 TTS 后端文件只放后端实现本身，不放 CLI 参数解析，不反向依赖 `src/tts/backends/__init__.py`。
- 后端选择、活动后端工厂、CLI 覆盖参数分发统一放在 `src/tts/backends/__init__.py`。
- 公共能力优先放在 `THS` 或 `src/tts` 下的公共模块，不把 Android 专属实现混进公共层。
- 命名保持一致，不为旧命名额外做兼容；配置 key、后端 key、CLI 参数前缀尽量统一。

## 重构

- 大文件优先按职责拆分，不做只移动代码但保留重复逻辑的拆分。
- GUI 和 CLI 有相同阅读/朗读编排时，优先抽公共逻辑，避免两边各维护一套。
- 如果移动或新增模块，记得同步检查 `src/meson.build` 和 `po/POTFILES`。

## 偏好

- 非必要不要保留兼容旧参数、旧 key、旧路径的分支。
- 能统一接口时优先统一接口，但不要把两种不同语义强行塞进一个名字含糊的实现里。
- 图标、按钮文案、设置 key 这类命名尽量直接，和实际后端或行为保持一致。

## Legado

- 开始阅读 Legado 时，始终使用远端阅读进度初始化当前位置，不做本地优先或本地覆盖远端的判断。
- Legado 阅读过程中，当前位置变动后需要同步回远端；是否累计本地阅读统计是另一层语义，不能因为 `way is None` 就停止远端位置同步。
- 只有初始化阶段可以禁止回写远端，避免刚打开书就把远端进度覆盖掉。
