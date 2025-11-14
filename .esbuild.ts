
import * as watcher from '@parcel/watcher';
import * as esbuild from 'esbuild';
import * as fs from 'fs';
import path from 'path';

const REPO_ROOT = path.join(__dirname);
const isDev = process.argv.includes("--dev");
const isWatch = process.argv.includes("--watch");
const isPreRelease = process.argv.includes("--prerelease");

const baseBuildOptions = {
    bundle: true,
    logLevel: "info",
    minify: !isDev,
    outdir: './dist',
    sourcemap: isDev ? 'linked' : false,
    sourcesContent: false,
    treeShaking: true
} satisfies esbuild.BuildOptions;

const baseNodeBuildOptions = {
    ...baseBuildOptions,
    external: [
        './package.json',
        ...(isDev ? [] : ['dotenv', 'source-map-support'])
    ],
    platform: 'node',
    mainFields: ['module', 'main'],
} satisfies esbuild.BuildOptions;

const nodeExtHostTestGlobs = [
    'extension/**/vscode/**/*.test.{ts,tsx}'
];

const testBundlePlugin: esbuild.Plugin = {
    name: 'testBundlePlugin',
    setup(build) {

    }
};

// importMetaPlugin
// shimVsCodeTypesPlugin

const nodeExtHostBuildOptions = {
    ...baseNodeBuildOptions,
    entryPoints: [
        { in: './extension/extension.ts', out: 'extension' }
    ],
    loader: { '.ps1': 'text' },
    plugins: [],
    external: [
        ...baseNodeBuildOptions.external,
        'vscode'
    ]
} satisfies esbuild.BuildOptions;


function applyPackageJsonPatch(isPreRelease: boolean) {
    const packagejsonPath = path.join(__dirname, './package.json');
    const json = JSON.parse(fs.readFileSync(packagejsonPath).toString());

    const newProps: any = {
        buildType: 'prod',
        isPreRelease,
    };

    const patchedPackageJson = Object.assign(json, newProps);

    // Remove fields which might reveal our development process
    delete patchedPackageJson['scripts'];
    delete patchedPackageJson['devDependencies'];
    delete patchedPackageJson['dependencies'];

    fs.writeFileSync(packagejsonPath, JSON.stringify(patchedPackageJson));
}
async function main() {
    if (!isDev) {
        applyPackageJsonPatch(isPreRelease);
    }
    if (isWatch) {
        const contexts: esbuild.BuildContext[] = [];

        const nodeExtHostContext = await esbuild.context(nodeExtHostBuildOptions);
        contexts.push(nodeExtHostContext);

        let debounce: NodeJS.Timeout | undefined;

        const rebuild = async () => {
            if (debounce) {
                clearTimeout(debounce);
            }

            debounce = setTimeout(async () => {
                console.log('[watch] build started');
                for (const ctx of contexts) {
                    try {
                        await ctx.cancel();
                        await ctx.rebuild();
                    } catch (error) {
                        console.log('[watch]', error);
                    }
                }
                console.log('[watch] build finished');
            }, 100);
        };
        watcher.subscribe(REPO_ROOT, (err, events) => {
            for (const event of events) {
                console.log(`File change detected: ${event.path}`);
            }
            rebuild();
        }, {
            ignore: [
                `**/.git/**`,
                `**/.simulation/**`,
                `**/test/outcome/**`,
                `.vscode-test/**`,
                `**/.venv/**`,
                `**/dist/**`,
                `**/node_modules/**`,
                `**/*.txt`,
                `**/baseline.json`,
                `**/baseline.old.json`,
                `**/*.w.json`,
                '**/*.sqlite',
                '**/*.sqlite-journal',
                'test/aml/out/**'
            ]
        });
        rebuild();
    }
    else {
        await Promise.all([
            esbuild.build(nodeExtHostBuildOptions)
        ]);

    }
}

main();