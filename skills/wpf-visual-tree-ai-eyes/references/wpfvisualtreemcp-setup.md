# WpfVisualTreeMcp 安装 / 接入 / 重新编译 patch 详细步骤

> 路径说明:下文 `<USER>` 指本机 Windows 用户名;WorkBuddy 用户技能/工具目录一般为 `C:\Users\<USER>\.workbuddy\`。

## 1. 安装(若 tools 目录不存在或需升级)

```bash
# 查最新 release(上游仓库 faze79/WPFVisualTreeMcp;沙箱内可用 node fetch 直连 api.github.com)
# 下载 WpfVisualTreeMcp-vX.X.X-win-x64.zip(例 v0.12.0)
# 解压到 C:\Users\<USER>\.workbuddy\tools\WpfVisualTreeMcp
#   结构: server\WpfVisualTreeMcp.Server.exe(MCP server + 一次性 CLI 双模式)
#         inspector\WpfVisualTreeMcp.Inspector.dll(net8.0, self-hosted 引用目标)
```

网络提示:curl/git 走代理可能被墙或 0 字节;GitHub API/下载用
`C:/Users/<USER>/.workbuddy/binaries/node/versions/<版本>/node.exe` 写原生 fetch 脚本直连。

## 2. 目标 app 接入(self-hosted, DEBUG-only)

### csproj(追加在 `</Project>` 前)
```xml
<PropertyGroup Condition="'$(Configuration)'=='Debug' And Exists('C:\Users\<USER>\.workbuddy\tools\WpfVisualTreeMcp\inspector\WpfVisualTreeMcp.Inspector.dll')">
  <DefineConstants>$(DefineConstants);WPFMCP_INSPECTOR</DefineConstants>
</PropertyGroup>
<ItemGroup Condition="'$(Configuration)'=='Debug' And Exists('C:\Users\<USER>\.workbuddy\tools\WpfVisualTreeMcp\inspector\WpfVisualTreeMcp.Inspector.dll')">
  <Reference Include="WpfVisualTreeMcp.Inspector">
    <HintPath>C:\Users\<USER>\.workbuddy\tools\WpfVisualTreeMcp\inspector\WpfVisualTreeMcp.Inspector.dll</HintPath>
    <Private>true</Private>
  </Reference>
  <Reference Include="WpfVisualTreeMcp.Shared">
    <HintPath>C:\Users\<USER>\.workbuddy\tools\WpfVisualTreeMcp\inspector\WpfVisualTreeMcp.Shared.dll</HintPath>
    <Private>true</Private>
  </Reference>
</ItemGroup>
```

### App.xaml.cs OnStartup(放在日志初始化之后)
```csharp
#if WPFMCP_INSPECTOR
        try
        {
            WpfVisualTreeMcp.Inspector.InspectorService.Initialize(Environment.ProcessId);
            AppLog.Info("inspector-ready");
        }
        catch (Exception inspectorEx) { AppLog.Info("inspector-init-failed: " + inspectorEx); }
#endif
```

要求:目标项目 TargetFramework 为 net8.0-windows 或更高(net9 可引用 net8 Inspector DLL)。

## 3. 重打 NaN patch(升级/重装 v0.12.0 后必做)

背景:release 的 Inspector.dll 有 bug——`PropertyReader.FormatValue` 的 primitive 分支
`return value.ToString()` 会把 double NaN/Infinity 裸输出(`"value":NaN`),Server 端
`JsonDocument.Parse` 崩,props 全量读取失败(element Unknown + properties 空)。

```bash
# 1) 下载 main 源码 zip(codeload.github.com/faze79/WPFVisualTreeMcp/zip/refs/heads/main),解压
# 2) 改 src/WpfVisualTreeMcp.Inspector/PropertyReader.cs 的 FormatValue primitive 分支:
#    在 value.ToString() 前插入:
#      if (value is double d && (double.IsNaN(d) || double.IsInfinity(d)))
#          return $"\"{d.ToString(System.Globalization.CultureInfo.InvariantCulture)}\"";
#      if (value is float f && (float.IsNaN(f) || float.IsInfinity(f)))
#          return $"\"{f.ToString(System.Globalization.CultureInfo.InvariantCulture)}\"";
# 3) 编译(沙箱内 dotnet 会被 NuGet 写盘拦截 → 需 dangerouslyDisableSandbox=true;
#    包缓存指工作区避免污染用户目录):
#    NUGET_PACKAGES="<工作区>/tmp_nuget" dotnet build -c Release -f net8.0-windows
# 4) 覆盖安装:
#    cp bin/Release/net8.0-windows/WpfVisualTreeMcp.Inspector.dll \
#       C:/Users/<USER>/.workbuddy/tools/WpfVisualTreeMcp/inspector/
#    (目标 app 的 bin/Debug 输出目录里的 Inspector.dll 副本也要覆盖)
# 5) 清理 tmp_nuget
```

验证 patch 生效:attach 后 `props` 至少能返回 `element.typeName`(patch 前直接崩/Unknown)。

## 4. CLI 验收常用命令与 JSON 解析

```bash
S="C:/Users/<USER>/.workbuddy/tools/WpfVisualTreeMcp/server/WpfVisualTreeMcp.Server.exe"
PY="C:/Users/<USER>/.workbuddy/binaries/python/versions/<版本>/python.exe"

# 连上(self-hosted 目标)
$S attach --pid <PID> --compact      # 期望 "Loaded (self-hosted)"

# 结构树美化打印
$S tree --pid <PID> --depth 12 --compact | $PY -c "
import json,sys
d=json.load(sys.stdin)
def walk(n,dep=0):
    t=n.get('typeName','').split('.')[-1]
    x=''
    for k in ('name','text'):
        if n.get(k): x+=f' [{k}={n[k][:40]}]'
    print('  '*dep+t+x)
    for c in n.get('children',[]): walk(c,dep+1)
walk(d.get('root',d))"

# 按 name / 文本 / 类型找元素(拿 handle + screenBounds)
$S find --pid <PID> --name ViewGrid --compact
$S find --pid <PID> --text 编辑 --compact
$S find --pid <PID> --type CardView --compact

# 模拟点击(进批量/开关状态)
$S click --pid <PID> --handle <H> --compact   # {"success":true,"method":"Invoke"}

# 量化:对比 screenBounds 算相对位置(勾选框距卡右缘/顶多少 px)
```

注意:每次交互后元素 handle 可能变化,重新 find;state 类验证用前后对比
(如批量模式:点编辑 → `find --name SelChk` 的 isVisible 从 False 变 True;再点回 False)。
