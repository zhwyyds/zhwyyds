/** demo 构建脚本：esbuild JS API 打包 MetricCard demo */
const path = require("path");
const esbuild = require("esbuild");

const here = __dirname;
// esbuild 模块解析的额外查找路径（依赖装在 managed workspace）
const EXTRA_NODE_MODULES = "/Users/heyuan/.workbuddy/binaries/node/workspace/node_modules";

esbuild
  .build({
    entryPoints: [path.join(here, "demo-entry.jsx")],
    bundle: true,
    outfile: path.join(here, "dist", "demo.js"),
    format: "iife",
    jsx: "automatic",
    loader: { ".jsx": "jsx" },
    nodePaths: [EXTRA_NODE_MODULES],
    logLevel: "warning",
  })
  .then(() => console.log("BUILD OK -> dist/demo.js"))
  .catch((e) => {
    console.error(e);
    process.exit(1);
  });
