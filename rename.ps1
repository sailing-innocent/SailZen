# rename.ps1
# 临时脚本：将当前目录下所有以 "Dendron" 开头的文件/文件夹重命名为以 "Sail" 开头；
# 并将名称中所有小写 "dendron" 替换为 "sail"。
# 注意：按路径深度从深到浅处理，避免父目录改名后子路径失效。

Get-ChildItem -Path . -Recurse -Force -ErrorAction SilentlyContinue |
    Where-Object { $_.Name.StartsWith('Dendron') -or $_.Name.Contains('dendron') } |
    Sort-Object -Property { $_.FullName.Length } -Descending |
    ForEach-Object {
        $oldName = $_.Name
        $newName = $oldName

        # 处理以 Dendron 开头的名称（区分大小写）
        if ($newName.StartsWith('Dendron')) {
            $newName = 'Sail' + $newName.Substring('Dendron'.Length)
        }

        # 处理所有小写 dendron 的出现（区分大小写）
        $newName = $newName.Replace('dendron', 'sail')

        if ($newName -ne $oldName) {
            try {
                Rename-Item -Path $_.FullName -NewName $newName -ErrorAction Stop
                Write-Host "Renamed: $($_.FullName) -> $newName"
            }
            catch {
                Write-Warning "Failed to rename $($_.FullName): $_"
            }
        }
    }
