package com.sailzen.app.core.rhythm

import android.content.Intent
import android.service.quicksettings.Tile
import android.service.quicksettings.TileService
import com.sailzen.app.MainActivity

/**
 * 通知栏快速捕获磁贴（M3）：
 * 点击 → 打开 MainActivity 并弹出快速捕获对话框（一句话 → kind=generic 交 AI 分拣）。
 */
class QuickCaptureTileService : TileService() {

    companion object {
        const val EXTRA_OPEN_CAPTURE = "com.sailzen.app.extra.OPEN_CAPTURE"
    }

    override fun onStartListening() {
        super.onStartListening()
        qsTile?.apply {
            state = Tile.STATE_INACTIVE
            updateTile()
        }
    }

    override fun onClick() {
        super.onClick()
        val intent = Intent(this, MainActivity::class.java).apply {
            addFlags(Intent.FLAG_ACTIVITY_NEW_TASK or Intent.FLAG_ACTIVITY_SINGLE_TOP)
            putExtra(EXTRA_OPEN_CAPTURE, true)
        }
        startActivityAndCollapse(intent)
    }
}
