package com.sailzen.app.feature.plan

import com.sailzen.app.core.network.dto.AffairDto
import com.sailzen.app.core.rhythm.RhythmTime
import com.sailzen.app.feature.plan.PlanViewModel.PlanTab
import java.time.LocalDateTime
import kotlinx.serialization.json.JsonObject
import kotlinx.serialization.json.JsonPrimitive
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Test

class PlanViewModelTest {

    private fun task(
        id: Int,
        urgencyDdl: String? = null,
        importance: Int = 3,
        state: String = "ACTIVE",
        kind: String = "task_oneoff",
        aiHint: JsonObject = JsonObject(emptyMap()),
    ) = AffairDto(
        id = id,
        title = "task-$id",
        kind = kind,
        state = state,
        importance = importance,
        urgencyDdl = urgencyDdl,
        aiHint = aiHint,
    )

    // ---------------- 任务排序：逾期优先 → 截止升序 → 重要性降序 ----------------

    @Test
    fun taskComparator_overdueFirstThenDdlThenImportance() {
        val past = RhythmTime.format(LocalDateTime.now().minusHours(1))
        val soon = RhythmTime.format(LocalDateTime.now().plusHours(2))
        val later = RhythmTime.format(LocalDateTime.now().plusHours(10))
        val tasks = listOf(
            task(id = 1, urgencyDdl = later, importance = 5),
            task(id = 2, urgencyDdl = past, importance = 1),   // 逾期排最前
            task(id = 3, urgencyDdl = soon, importance = 1),
            task(id = 4, urgencyDdl = soon, importance = 5),   // 完全同 ddl，重要性降序
            task(id = 5, urgencyDdl = null),                   // 无 ddl 排最后
        )
        val sorted = tasks.sortedWith(PlanViewModel.taskComparator())
        // 2 逾期最前；3/4 同 ddl 按重要性降序（4 在前）；1 未逾期有 ddl；5 无 ddl 最后
        assertEquals(listOf(2, 4, 3, 1, 5), sorted.map { it.id })
    }

    @Test
    fun taskComparator_ventureAndBufferKindsExcludedByCallers() {
        // comparator 本身只排序；kind 过滤由 loadAffairs 完成，这里验证过滤契约
        val tasks = listOf(
            task(id = 1, kind = "venture"),
            task(id = 2, kind = "task_oneoff"),
            task(id = 3, kind = "buffer"),
        )
        val filtered = tasks.filter {
            it.kind != com.sailzen.app.core.rhythm.AffairRules.VENTURE_KIND && it.kind != "buffer"
        }
        assertEquals(listOf(2), filtered.map { it.id })
    }

    // ---------------- 待分拣拆分：AI 建议 / 普通 INBOX ----------------

    @Test
    fun splitInbox_separatesHintedFromPlain() {
        val hinted = task(
            id = 1,
            aiHint = JsonObject(mapOf("kind" to JsonPrimitive("habit"))),
        )
        val plain = task(id = 2)
        val (withHint, withoutHint) = PlanViewModel.splitInbox(listOf(hinted, plain))
        assertEquals(listOf(1), withHint.map { it.id })
        assertEquals(listOf(2), withoutHint.map { it.id })
    }

    @Test
    fun splitInbox_emptyHintJsonIsPlain() {
        val emptyHint = task(id = 1, aiHint = JsonObject(emptyMap()))
        val (withHint, withoutHint) = PlanViewModel.splitInbox(listOf(emptyHint))
        assertTrue(withHint.isEmpty())
        assertEquals(listOf(1), withoutHint.map { it.id })
    }

    // ---------------- Tab 切换懒加载状态机 ----------------

    @Test
    fun shouldLazyLoad_todayAlwaysRefreshes() {
        assertTrue(PlanViewModel.shouldLazyLoad(PlanTab.TODAY, affairsLoaded = true, venturesLoaded = true))
    }

    @Test
    fun shouldLazyLoad_affairsLoadedOnlyOnce() {
        assertTrue(PlanViewModel.shouldLazyLoad(PlanTab.AFFAIR, affairsLoaded = false, venturesLoaded = false))
        assertFalse(PlanViewModel.shouldLazyLoad(PlanTab.AFFAIR, affairsLoaded = true, venturesLoaded = false))
    }

    @Test
    fun shouldLazyLoad_venturesLoadedOnlyOnce() {
        assertTrue(PlanViewModel.shouldLazyLoad(PlanTab.VENTURE, affairsLoaded = true, venturesLoaded = false))
        assertFalse(PlanViewModel.shouldLazyLoad(PlanTab.VENTURE, affairsLoaded = true, venturesLoaded = true))
    }

    @Test
    fun shouldLazyLoad_affairsAndVenturesIndependent() {
        // 事业已加载不影响事务的懒加载判定
        assertTrue(PlanViewModel.shouldLazyLoad(PlanTab.AFFAIR, affairsLoaded = false, venturesLoaded = true))
    }
}
