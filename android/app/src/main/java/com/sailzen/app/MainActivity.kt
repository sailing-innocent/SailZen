package com.sailzen.app

import android.Manifest
import android.content.Intent
import android.content.pm.PackageManager
import android.os.Build
import android.os.Bundle
import androidx.activity.ComponentActivity
import androidx.activity.compose.rememberLauncherForActivityResult
import androidx.activity.compose.setContent
import androidx.activity.result.contract.ActivityResultContracts
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableIntStateOf
import androidx.navigation.compose.rememberNavController
import com.sailzen.app.core.reminder.ReminderActionReceiver
import com.sailzen.app.ui.navigation.Routes
import com.sailzen.app.ui.navigation.SailZenNavGraph
import com.sailzen.app.ui.theme.SailZenTheme

class MainActivity : ComponentActivity() {

    /** 通知跳入的 reminder_id（-1 表示无） */
    private val reminderIdState = mutableIntStateOf(-1)

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        handleIntent(intent)
        setContent {
            SailZenTheme {
                val navController = rememberNavController()

                // 通知权限请求（API 33+）
                val permissionLauncher = rememberLauncherForActivityResult(
                    ActivityResultContracts.RequestPermission(),
                ) { }
                LaunchedEffect(Unit) {
                    if (Build.VERSION.SDK_INT >= 33 &&
                        checkSelfPermission(Manifest.permission.POST_NOTIFICATIONS) !=
                        PackageManager.PERMISSION_GRANTED
                    ) {
                        permissionLauncher.launch(Manifest.permission.POST_NOTIFICATIONS)
                    }
                }

                // 通知跳入：导航到 Inbox 并高亮该提醒
                val highlightId by reminderIdState
                LaunchedEffect(highlightId) {
                    if (highlightId > 0) {
                        navController.navigate(Routes.inbox(highlightId))
                    }
                }

                SailZenNavGraph(navController = navController)
            }
        }
    }

    override fun onNewIntent(intent: Intent) {
        super.onNewIntent(intent)
        handleIntent(intent)
    }

    private fun handleIntent(intent: Intent?) {
        val reminderId = intent?.getIntExtra(ReminderActionReceiver.EXTRA_REMINDER_ID, -1) ?: -1
        if (reminderId > 0) {
            reminderIdState.intValue = reminderId
        }
    }
}
