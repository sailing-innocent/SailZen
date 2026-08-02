package com.sailzen.app.ui.navigation

import androidx.compose.runtime.Composable
import androidx.navigation.NavHostController
import androidx.navigation.NavType
import androidx.navigation.compose.NavHost
import androidx.navigation.compose.composable
import androidx.navigation.navArgument
import com.sailzen.app.feature.inbox.InboxScreen
import com.sailzen.app.feature.settings.SettingsScreen

object Routes {
    const val INBOX = "inbox?reminder_id={reminder_id}"
    const val SETTINGS = "settings"

    fun inbox(reminderId: Int = -1) = "inbox?reminder_id=$reminderId"
}

@Composable
fun SailZenNavGraph(navController: NavHostController) {
    NavHost(navController = navController, startDestination = Routes.INBOX) {
        composable(
            route = Routes.INBOX,
            arguments = listOf(
                navArgument("reminder_id") {
                    type = NavType.IntType
                    defaultValue = -1
                },
            ),
        ) { entry ->
            InboxScreen(
                highlightReminderId = entry.arguments?.getInt("reminder_id") ?: -1,
                onOpenSettings = { navController.navigate(Routes.SETTINGS) },
            )
        }
        composable(Routes.SETTINGS) {
            SettingsScreen(onBack = { navController.popBackStack() })
        }
    }
}
