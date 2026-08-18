package com.sailzen.app.ui.navigation

import androidx.compose.foundation.layout.padding
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.CheckCircle
import androidx.compose.material.icons.filled.DateRange
import androidx.compose.material.icons.filled.Email
import androidx.compose.material.icons.filled.Favorite
import androidx.compose.material.icons.filled.Star
import androidx.compose.material3.Icon
import androidx.compose.material3.NavigationBar
import androidx.compose.material3.NavigationBarItem
import androidx.compose.material3.Scaffold
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.ui.Modifier
import androidx.navigation.NavHostController
import androidx.navigation.NavType
import androidx.navigation.compose.NavHost
import androidx.navigation.compose.composable
import androidx.navigation.compose.currentBackStackEntryAsState
import androidx.navigation.navArgument
import com.sailzen.app.feature.affair.AffairDetailScreen
import com.sailzen.app.feature.affair.AffairHomeScreen
import com.sailzen.app.feature.checkin.CheckinScreen
import com.sailzen.app.feature.diet.DietScreen
import com.sailzen.app.feature.exercise.ExerciseScreen
import com.sailzen.app.feature.health.HealthCheckinScreen
import com.sailzen.app.feature.health.HealthHomeScreen
import com.sailzen.app.feature.health.medication.MedicationScreen
import com.sailzen.app.feature.health.sleep.SleepScheduleScreen
import com.sailzen.app.feature.health.weight.WeightCurveScreen
import com.sailzen.app.feature.health.weight.WeightPlanScreen
import com.sailzen.app.feature.inbox.InboxScreen
import com.sailzen.app.feature.settings.SettingsScreen
import com.sailzen.app.feature.timeline.TimelineScreen

object Routes {
    const val TIMELINE = "timeline"
    const val CHECKIN = "checkin"
    const val AFFAIR = "affair"
    const val AFFAIR_DETAIL = "affair_detail/{affair_id}"
    const val HEALTH = "health"
    const val HEALTH_WEIGHT_CURVE = "health_weight_curve"
    const val HEALTH_WEIGHT_PLAN = "health_weight_plan"
    const val HEALTH_MEDICATION = "health_medication"
    const val HEALTH_SLEEP = "health_sleep"
    const val HEALTH_DIET = "health_diet"
    const val HEALTH_EXERCISE = "health_exercise"
    const val HEALTH_CHECKIN = "health_checkin?type={type}"
    const val INBOX = "inbox?reminder_id={reminder_id}"
    const val SETTINGS = "settings"

    fun inbox(reminderId: Int = -1) = "inbox?reminder_id=$reminderId"
    fun healthCheckin(type: String = "weight") = "health_checkin?type=$type"
    fun affairDetail(affairId: Int) = "affair_detail/$affairId"
}

private data class TabItem(
    val route: String,
    val label: String,
    val icon: androidx.compose.ui.graphics.vector.ImageVector,
)

private val TABS = listOf(
    TabItem(Routes.TIMELINE, "时间线", Icons.Default.DateRange),
    TabItem(Routes.CHECKIN, "打卡", Icons.Default.CheckCircle),
    TabItem(Routes.AFFAIR, "事业", Icons.Default.Star),
    TabItem("inbox_tab", "收件箱", Icons.Default.Email),
    TabItem(Routes.HEALTH, "健康", Icons.Default.Favorite),
)

@Composable
fun SailZenNavGraph(
    navController: NavHostController,
    openCapture: Boolean = false,
) {
    val backStackEntry by navController.currentBackStackEntryAsState()
    val currentRoute = backStackEntry?.destination?.route

    Scaffold(
        bottomBar = {
            // 设置页不显示底栏
            if (currentRoute != Routes.SETTINGS) {
                NavigationBar {
                    TABS.forEach { tab ->
                        val selected = when (tab.route) {
                            "inbox_tab" -> currentRoute == Routes.INBOX
                            else -> currentRoute == tab.route
                        }
                        NavigationBarItem(
                            selected = selected,
                            onClick = {
                                val target = if (tab.route == "inbox_tab") Routes.inbox() else tab.route
                                navController.navigate(target) {
                                    popUpTo(Routes.TIMELINE) { saveState = true }
                                    launchSingleTop = true
                                    restoreState = true
                                }
                            },
                            icon = { Icon(tab.icon, contentDescription = tab.label) },
                            label = { Text(tab.label) },
                        )
                    }
                }
            }
        },
    ) { padding ->
        NavHost(
            navController = navController,
            startDestination = Routes.TIMELINE,
            modifier = Modifier.padding(padding),
        ) {
            composable(Routes.TIMELINE) {
                TimelineScreen(
                    onOpenSettings = { navController.navigate(Routes.SETTINGS) },
                    openCapture = openCapture,
                )
            }
            composable(Routes.CHECKIN) {
                CheckinScreen(
                    onOpenHealthCheckin = {
                        navController.navigate(Routes.healthCheckin())
                    },
                )
            }
            composable(Routes.AFFAIR) {
                AffairHomeScreen(
                    onOpenDetail = { affairId ->
                        navController.navigate(Routes.affairDetail(affairId))
                    },
                )
            }
            composable(
                route = Routes.AFFAIR_DETAIL,
                arguments = listOf(
                    navArgument("affair_id") { type = NavType.IntType },
                ),
            ) { entry ->
                val affairId = entry.arguments?.getInt("affair_id") ?: -1
                AffairDetailScreen(
                    affairId = affairId,
                    onBack = { navController.popBackStack() },
                    onOpenChild = { childId ->
                        navController.navigate(Routes.affairDetail(childId))
                    },
                )
            }
            composable(Routes.HEALTH) {
                HealthHomeScreen(
                    onNavigate = { route -> navController.navigate(route) },
                    onOpenHealthCheckin = { type ->
                        navController.navigate(Routes.healthCheckin(type.name))
                    },
                )
            }
            composable(Routes.HEALTH_WEIGHT_CURVE) { WeightCurveScreen(onBack = { navController.popBackStack() }) }
            composable(Routes.HEALTH_WEIGHT_PLAN) { WeightPlanScreen(onBack = { navController.popBackStack() }) }
            composable(Routes.HEALTH_MEDICATION) { MedicationScreen(onBack = { navController.popBackStack() }) }
            composable(Routes.HEALTH_SLEEP) { SleepScheduleScreen(onBack = { navController.popBackStack() }) }
            composable(Routes.HEALTH_DIET) { DietScreen(onBack = { navController.popBackStack() }) }
            composable(Routes.HEALTH_EXERCISE) { ExerciseScreen(onBack = { navController.popBackStack() }) }
            composable(
                route = Routes.HEALTH_CHECKIN,
                arguments = listOf(
                    navArgument("type") {
                        type = NavType.StringType
                        defaultValue = "weight"
                    },
                ),
            ) { entry ->
                val typeName = entry.arguments?.getString("type") ?: "weight"
                HealthCheckinScreen(
                    initialType = runCatching {
                        com.sailzen.app.core.network.dto.InfoCollectionType.valueOf(typeName)
                    }.getOrNull(),
                    onBack = { navController.popBackStack() },
                )
            }
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
}
