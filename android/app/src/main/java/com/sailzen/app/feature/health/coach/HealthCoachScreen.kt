package com.sailzen.app.feature.health.coach

import android.net.Uri
import androidx.activity.compose.rememberLauncherForActivityResult
import androidx.activity.result.PickVisualMediaRequest
import androidx.activity.result.contract.ActivityResultContracts
import androidx.compose.foundation.horizontalScroll
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.PaddingValues
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.rememberScrollState
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.automirrored.filled.ArrowBack
import androidx.compose.material.icons.automirrored.filled.Send
import androidx.compose.material.icons.filled.AutoAwesome
import androidx.compose.material.icons.filled.Close
import androidx.compose.material.icons.filled.PhotoCamera
import androidx.compose.material.icons.filled.PhotoLibrary
import androidx.compose.material.icons.filled.Refresh
import androidx.compose.material3.AssistChip
import androidx.compose.material3.Button
import androidx.compose.material3.Card
import androidx.compose.material3.CardDefaults
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.FilledTonalButton
import androidx.compose.material3.FilledTonalIconButton
import androidx.compose.material3.FilterChip
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.LinearProgressIndicator
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.Scaffold
import androidx.compose.material3.SnackbarHost
import androidx.compose.material3.SnackbarHostState
import androidx.compose.material3.Surface
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.material3.TopAppBar
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.collectAsState
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableIntStateOf
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.core.content.FileProvider
import androidx.lifecycle.viewmodel.compose.viewModel
import com.sailzen.app.core.network.dto.DailyReportDto
import com.sailzen.app.core.network.dto.ImageIntakeDraftDto
import com.sailzen.app.core.network.dto.TickTicketDto
import java.io.File

private data class QuickCategoryChip(
    val label: String,
    val category: String,
    val mealType: String? = null,
)

private val SILENT_CHIPS = listOf(
    QuickCategoryChip("早餐", "diet", "breakfast"),
    QuickCategoryChip("午餐", "diet", "lunch"),
    QuickCategoryChip("晚餐", "diet", "dinner"),
    QuickCategoryChip("加餐", "diet", "snack"),
    QuickCategoryChip("日常状态", "daily_info", null),
)

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun HealthCoachScreen(
    onBack: () -> Unit,
    onQuickLogWeight: () -> Unit,
    viewModel: HealthCoachViewModel = viewModel(),
) {
    val context = LocalContext.current
    val state by viewModel.uiState.collectAsState()
    val snackbarHostState = remember { SnackbarHostState() }

    var selectedChipIndex by remember { mutableIntStateOf(1) }
    var silentInput by remember { mutableStateOf("") }
    var imageNote by remember { mutableStateOf("") }
    var forceOcr by remember { mutableStateOf(false) }
    var reportExpanded by remember { mutableStateOf(false) }

    // 临时记录本次选图/拍照是否关联某张待回票据
    var pendingTicketIdForImage by remember { mutableStateOf<Int?>(null) }
    var pendingCameraUri by remember { mutableStateOf<Uri?>(null) }

    // 系统相册选图（Photo Picker，免存储权限）
    val photoPickerLauncher = rememberLauncherForActivityResult(
        contract = ActivityResultContracts.PickVisualMedia(),
    ) { uri: Uri? ->
        val ticketId = pendingTicketIdForImage
        pendingTicketIdForImage = null
        if (uri != null) {
            val noteToSend = imageNote
            imageNote = ""
            viewModel.analyzeImageUri(
                uri = uri,
                note = noteToSend,
                sourceChannel = "android",
                ticketId = ticketId,
                forceOcr = forceOcr,
            )
        }
    }

    // 系统相机拍照（FileProvider 落盘 cacheDir/captures/，免 CAMERA 权限）
    val takePictureLauncher = rememberLauncherForActivityResult(
        contract = ActivityResultContracts.TakePicture(),
    ) { success: Boolean ->
        val uri = pendingCameraUri
        val ticketId = pendingTicketIdForImage
        pendingCameraUri = null
        pendingTicketIdForImage = null
        if (success && uri != null) {
            val noteToSend = imageNote
            imageNote = ""
            viewModel.analyzeImageUri(
                uri = uri,
                note = noteToSend,
                sourceChannel = "android",
                ticketId = ticketId,
                forceOcr = forceOcr,
            )
        }
    }

    fun launchGallery(ticketId: Int? = null) {
        pendingTicketIdForImage = ticketId
        photoPickerLauncher.launch(
            PickVisualMediaRequest(ActivityResultContracts.PickVisualMedia.ImageOnly),
        )
    }

    fun launchCamera(ticketId: Int? = null) {
        val dir = File(context.cacheDir, "captures").apply { mkdirs() }
        dir.listFiles()?.sortedByDescending { it.lastModified() }?.drop(8)?.forEach { it.delete() }
        val file = File(dir, "cam_${System.currentTimeMillis()}.jpg")
        val uri = FileProvider.getUriForFile(context, "${context.packageName}.fileprovider", file)
        pendingCameraUri = uri
        pendingTicketIdForImage = ticketId
        takePictureLauncher.launch(uri)
    }

    LaunchedEffect(state.feedbackMessage) {
        val msg = state.feedbackMessage ?: return@LaunchedEffect
        snackbarHostState.showSnackbar(msg)
        viewModel.clearFeedback()
    }

    val activeReport = state.reports.firstOrNull { it.reportDate == state.selectedReportDate }
        ?: state.summary?.latestReport

    Scaffold(
        topBar = {
            TopAppBar(
                title = { Text("SailTick Personal Agent") },
                navigationIcon = {
                    IconButton(onClick = onBack) {
                        Icon(Icons.AutoMirrored.Filled.ArrowBack, contentDescription = "返回")
                    }
                },
                actions = {
                    TextButton(onClick = onQuickLogWeight) { Text("记体重") }
                    IconButton(onClick = { viewModel.refresh() }) {
                        Icon(Icons.Default.Refresh, contentDescription = "刷新")
                    }
                },
            )
        },
        snackbarHost = { SnackbarHost(snackbarHostState) },
    ) { padding ->
        Column(
            modifier = Modifier
                .fillMaxSize()
                .padding(padding),
        ) {
            if (state.loading || state.analyzingImage) {
                LinearProgressIndicator(modifier = Modifier.fillMaxWidth())
            }

            LazyColumn(
                modifier = Modifier
                    .fillMaxSize()
                    .padding(horizontal = 16.dp),
                verticalArrangement = Arrangement.spacedBy(12.dp),
                contentPadding = PaddingValues(vertical = 12.dp),
            ) {
                // 非阻塞错误提示卡片（遵循规范 §2.3，绝不弹窗锁死）
                if (!state.errorBanner.isNullOrBlank()) {
                    item {
                        Card(
                            modifier = Modifier.fillMaxWidth(),
                            colors = CardDefaults.cardColors(
                                containerColor = MaterialTheme.colorScheme.errorContainer,
                            ),
                        ) {
                            Row(
                                modifier = Modifier
                                    .fillMaxWidth()
                                    .padding(12.dp),
                                verticalAlignment = Alignment.CenterVertically,
                                horizontalArrangement = Arrangement.SpaceBetween,
                            ) {
                                Text(
                                    state.errorBanner.orEmpty(),
                                    style = MaterialTheme.typography.bodySmall,
                                    color = MaterialTheme.colorScheme.onErrorContainer,
                                    modifier = Modifier.weight(1f),
                                )
                                TextButton(onClick = { viewModel.dismissErrorBanner() }) {
                                    Text("忽略")
                                }
                            }
                        }
                    }
                }

                // 0a. 随时对话（日程 · 项目 · 健康 · 提醒统一随身快脑）
                item {
                    PersonalAgentQuickChatCard(
                        busy = state.quickChatBusy,
                        reply = state.quickChatReply,
                        isAsyncFallback = state.quickChatAsyncFallback,
                        onSend = { viewModel.sendQuickChat(it) },
                        onDismissReply = { viewModel.clearQuickChatReply() },
                    )
                }

                // 0b. 拍照 / 选截图 AI 智能识图记录
                item {
                    ImageIntakeCaptureCard(
                        note = imageNote,
                        onNoteChange = { imageNote = it },
                        forceOcr = forceOcr,
                        onToggleForceOcr = { forceOcr = !forceOcr },
                        analyzing = state.analyzingImage,
                        pendingDrafts = state.summary?.pendingIntakeDrafts.orEmpty(),
                        onPickGallery = { launchGallery(null) },
                        onTakePhoto = { launchCamera(null) },
                        onOpenDraft = { draft -> viewModel.openPendingDraft(draft) },
                    )
                }

                // 1. 待回复的 AI 渐进式提问（支持文字、快捷词或直接传图回复）
                val pendingTickets = state.summary?.pendingTickets.orEmpty()
                if (pendingTickets.isNotEmpty()) {
                    item {
                        Text(
                            "教练提问（${state.summary?.pendingTicketCount ?: pendingTickets.size}）",
                            style = MaterialTheme.typography.titleMedium,
                        )
                    }
                    items(pendingTickets, key = { it.id }) { ticket ->
                        CoachQuestionCard(
                            ticket = ticket,
                            sending = state.sending || state.analyzingImage,
                            onReply = { reply -> viewModel.replyTicket(ticket.id, reply) },
                            onReplyWithImage = { launchGallery(ticket.id) },
                            onSnooze = { viewModel.snoozeTicket(ticket.id) },
                        )
                    }
                }

                // 2. 随手记餐饮 / 发文字消息（静默收集）
                item {
                    Card(modifier = Modifier.fillMaxWidth()) {
                        Column(
                            modifier = Modifier.padding(14.dp),
                            verticalArrangement = Arrangement.spacedBy(8.dp),
                        ) {
                            Text(
                                "文字随手记 / 发消息",
                                style = MaterialTheme.typography.titleMedium,
                                fontWeight = FontWeight.SemiBold,
                            )
                            Text(
                                "不想传图时也可直接发一句吃过什么或今天的状态，AI 会在每晚睡前日报中统一整合。",
                                style = MaterialTheme.typography.bodySmall,
                                color = MaterialTheme.colorScheme.onSurfaceVariant,
                            )
                            Row(
                                modifier = Modifier
                                    .fillMaxWidth()
                                    .horizontalScroll(rememberScrollState()),
                                horizontalArrangement = Arrangement.spacedBy(8.dp),
                            ) {
                                SILENT_CHIPS.forEachIndexed { index, chip ->
                                    FilterChip(
                                        selected = selectedChipIndex == index,
                                        onClick = { selectedChipIndex = index },
                                        label = { Text(chip.label) },
                                    )
                                }
                            }
                            OutlinedTextField(
                                value = silentInput,
                                onValueChange = { silentInput = it },
                                modifier = Modifier.fillMaxWidth(),
                                placeholder = { Text("如：午饭食堂鸡胸肉+半碗米饭+西兰花") },
                                minLines = 2,
                            )
                            Row(
                                modifier = Modifier.fillMaxWidth(),
                                horizontalArrangement = Arrangement.End,
                            ) {
                                Button(
                                    enabled = silentInput.isNotBlank() && !state.sending,
                                    onClick = {
                                        val chip = SILENT_CHIPS[selectedChipIndex]
                                        viewModel.sendSilentMessage(
                                            content = silentInput,
                                            category = chip.category,
                                            mealType = chip.mealType,
                                        )
                                        silentInput = ""
                                    },
                                ) {
                                    Text("静默记录")
                                }
                            }
                            val todayMsgs = state.summary?.todayMessages.orEmpty()
                            if (todayMsgs.isNotEmpty()) {
                                Text(
                                    "今日已收集（${todayMsgs.size}）：",
                                    style = MaterialTheme.typography.labelMedium,
                                    color = MaterialTheme.colorScheme.onSurfaceVariant,
                                )
                                todayMsgs.take(5).forEach { m ->
                                    val tag = if (m.status == "ingested") "已整合" else "待日报整合"
                                    Text(
                                        "• ${m.content}  [$tag]",
                                        style = MaterialTheme.typography.bodySmall,
                                    )
                                }
                            }
                        }
                    }
                }

                // 3. 每日睡前体重与健康日报
                item {
                    Text("每日睡前体重与健康日报", style = MaterialTheme.typography.titleMedium)
                }
                if (state.reports.size > 1) {
                    item {
                        Row(
                            modifier = Modifier
                                .fillMaxWidth()
                                .horizontalScroll(rememberScrollState()),
                            horizontalArrangement = Arrangement.spacedBy(8.dp),
                        ) {
                            state.reports.take(7).forEach { r ->
                                FilterChip(
                                    selected = activeReport?.reportDate == r.reportDate,
                                    onClick = { viewModel.selectReport(r.reportDate) },
                                    label = { Text(r.reportDate.takeLast(5)) },
                                )
                            }
                        }
                    }
                }
                item {
                    DailyReportCard(
                        report = activeReport,
                        expanded = reportExpanded,
                        onToggleExpand = { reportExpanded = !reportExpanded },
                    )
                }
                item { Spacer(Modifier.height(48.dp)) }
            }
        }
    }

    // 弹出式 AI 识图确认与微调卡片
    val activeDraft = state.activeDraft
    if (activeDraft != null) {
        ImageIntakeConfirmSheet(
            draft = activeDraft,
            entries = state.draftEntries,
            summary = state.draftSummary,
            replyText = state.draftReplyText,
            previewBytes = state.previewImageBytes,
            committing = state.committingDraft,
            onDismiss = { viewModel.closeDraftSheet() },
            onSummaryChange = { viewModel.updateDraftSummary(it) },
            onReplyTextChange = { viewModel.updateDraftReplyText(it) },
            onToggleEntry = { idx, checked -> viewModel.toggleEntrySelected(idx, checked) },
            onEntryKindChange = { idx, kind -> viewModel.updateEntryKind(idx, kind) },
            onEntryTitleChange = { idx, title -> viewModel.updateEntryTitle(idx, title) },
            onEntryFieldChange = { idx, key, value -> viewModel.updateEntryDataField(idx, key, value) },
            onCommit = { viewModel.commitActiveDraft() },
            onDiscard = { viewModel.discardActiveDraft() },
        )
    }
}

@Composable
private fun ImageIntakeCaptureCard(
    note: String,
    onNoteChange: (String) -> Unit,
    forceOcr: Boolean,
    onToggleForceOcr: () -> Unit,
    analyzing: Boolean,
    pendingDrafts: List<ImageIntakeDraftDto>,
    onPickGallery: () -> Unit,
    onTakePhoto: () -> Unit,
    onOpenDraft: (ImageIntakeDraftDto) -> Unit,
) {
    Card(
        modifier = Modifier.fillMaxWidth(),
        colors = CardDefaults.cardColors(
            containerColor = MaterialTheme.colorScheme.primaryContainer.copy(alpha = 0.32f),
        ),
    ) {
        Column(
            modifier = Modifier.padding(14.dp),
            verticalArrangement = Arrangement.spacedBy(8.dp),
        ) {
            Text(
                "拍照 / 截图 AI 识图记录",
                style = MaterialTheme.typography.titleMedium,
                fontWeight = FontWeight.SemiBold,
            )
            Text(
                "支持食堂菜单、外卖订单、餐盘实拍、手表睡眠/运动截图、体重秤、自拍气色——识别后由你确认再落库，也可直接从其他 App 点「分享 → SailZen」。",
                style = MaterialTheme.typography.bodySmall,
                color = MaterialTheme.colorScheme.onSurfaceVariant,
            )
            OutlinedTextField(
                value = note,
                onValueChange = onNoteChange,
                modifier = Modifier.fillMaxWidth(),
                placeholder = { Text("可选备注：如「午饭打算在这菜单里挑」") },
                singleLine = true,
                enabled = !analyzing,
            )
            Row(
                modifier = Modifier.fillMaxWidth(),
                horizontalArrangement = Arrangement.spacedBy(8.dp),
            ) {
                Button(
                    onClick = onPickGallery,
                    enabled = !analyzing,
                    modifier = Modifier.weight(1f),
                ) {
                    Icon(Icons.Default.PhotoLibrary, contentDescription = null, modifier = Modifier.size(18.dp))
                    Spacer(Modifier.size(6.dp))
                    Text("选截图/相册")
                }
                FilledTonalButton(
                    onClick = onTakePhoto,
                    enabled = !analyzing,
                    modifier = Modifier.weight(1f),
                ) {
                    Icon(Icons.Default.PhotoCamera, contentDescription = null, modifier = Modifier.size(18.dp))
                    Spacer(Modifier.size(6.dp))
                    Text("拍照记录")
                }
            }
            Row(
                modifier = Modifier.fillMaxWidth(),
                verticalAlignment = Alignment.CenterVertically,
                horizontalArrangement = Arrangement.SpaceBetween,
            ) {
                FilterChip(
                    selected = forceOcr,
                    onClick = onToggleForceOcr,
                    enabled = !analyzing,
                    label = { Text("叠加 OCR（长菜单/密字图）", style = MaterialTheme.typography.labelSmall) },
                )
                if (analyzing) {
                    Text(
                        "DeepSeek 识图中…",
                        style = MaterialTheme.typography.labelMedium,
                        color = MaterialTheme.colorScheme.primary,
                    )
                }
            }

            // 若存在未确认的草稿（例如刚从电脑/其他入口上传尚未确认），可一键打开继续确认
            if (pendingDrafts.isNotEmpty()) {
                Text(
                    "待确认识图草稿（${pendingDrafts.size}）：",
                    style = MaterialTheme.typography.labelMedium,
                    color = MaterialTheme.colorScheme.primary,
                )
                pendingDrafts.take(3).forEach { d ->
                    OutlinedButton(
                        onClick = { onOpenDraft(d) },
                        modifier = Modifier.fillMaxWidth(),
                    ) {
                        Text(
                            "继续确认：${d.summary.ifBlank { "草稿 #${d.id}" }}",
                            maxLines = 1,
                        )
                    }
                }
            }
        }
    }
}

@Composable
private fun CoachQuestionCard(
    ticket: TickTicketDto,
    sending: Boolean,
    onReply: (String) -> Unit,
    onReplyWithImage: () -> Unit,
    onSnooze: () -> Unit,
) {
    var draft by remember(ticket.id) { mutableStateOf("") }
    val quickReplies = remember(ticket.id, ticket.meta) { ticket.quickReplies() }

    Card(
        modifier = Modifier.fillMaxWidth(),
        colors = CardDefaults.cardColors(
            containerColor = MaterialTheme.colorScheme.secondaryContainer.copy(alpha = 0.55f),
        ),
    ) {
        Column(
            modifier = Modifier.padding(14.dp),
            verticalArrangement = Arrangement.spacedBy(8.dp),
        ) {
            Text(
                ticket.title,
                style = MaterialTheme.typography.titleSmall,
                fontWeight = FontWeight.SemiBold,
            )
            if (ticket.body.isNotBlank()) {
                Text(ticket.body, style = MaterialTheme.typography.bodySmall)
            }
            if (quickReplies.isNotEmpty()) {
                Row(
                    modifier = Modifier
                        .fillMaxWidth()
                        .horizontalScroll(rememberScrollState()),
                    horizontalArrangement = Arrangement.spacedBy(8.dp),
                ) {
                    quickReplies.forEach { qr ->
                        AssistChip(
                            onClick = { onReply(qr) },
                            label = { Text(qr) },
                        )
                    }
                }
            }
            OutlinedTextField(
                value = draft,
                onValueChange = { draft = it },
                modifier = Modifier.fillMaxWidth(),
                placeholder = { Text("简短回复，或点下方「传图回复」…") },
                singleLine = true,
            )
            Row(
                modifier = Modifier.fillMaxWidth(),
                horizontalArrangement = Arrangement.spacedBy(8.dp, Alignment.End),
            ) {
                OutlinedButton(onClick = onReplyWithImage, enabled = !sending) {
                    Icon(Icons.Default.PhotoLibrary, contentDescription = null, modifier = Modifier.size(16.dp))
                    Spacer(Modifier.size(4.dp))
                    Text("传图回复")
                }
                OutlinedButton(onClick = onSnooze, enabled = !sending) {
                    Text("暂缓24h")
                }
                Button(
                    enabled = draft.isNotBlank() && !sending,
                    onClick = {
                        onReply(draft)
                        draft = ""
                    },
                ) {
                    Text("回复")
                }
            }
        }
    }
}

@Composable
private fun DailyReportCard(
    report: DailyReportDto?,
    expanded: Boolean,
    onToggleExpand: () -> Unit,
) {
    Card(modifier = Modifier.fillMaxWidth()) {
        Column(
            modifier = Modifier.padding(14.dp),
            verticalArrangement = Arrangement.spacedBy(8.dp),
        ) {
            if (report == null) {
                Text(
                    "暂无睡前日报。SailTick 会在每晚睡前整合当天体重、餐饮记录与 AI 动态计划进展并推送到这里。",
                    style = MaterialTheme.typography.bodyMedium,
                    color = MaterialTheme.colorScheme.onSurfaceVariant,
                )
                return@Column
            }
            Row(
                modifier = Modifier.fillMaxWidth(),
                horizontalArrangement = Arrangement.SpaceBetween,
                verticalAlignment = Alignment.CenterVertically,
            ) {
                Text(
                    report.title,
                    style = MaterialTheme.typography.titleSmall,
                    fontWeight = FontWeight.SemiBold,
                    modifier = Modifier.weight(1f),
                )
                Text(
                    report.reportDate,
                    style = MaterialTheme.typography.labelSmall,
                    color = MaterialTheme.colorScheme.onSurfaceVariant,
                )
            }
            if (report.summary.isNotBlank()) {
                Text(report.summary, style = MaterialTheme.typography.bodyMedium)
            }
            if (report.tomorrowFocus.isNotEmpty()) {
                Text(
                    "明日轻量建议：",
                    style = MaterialTheme.typography.labelMedium,
                    color = MaterialTheme.colorScheme.primary,
                )
                report.tomorrowFocus.forEach { tip ->
                    Text("• $tip", style = MaterialTheme.typography.bodySmall)
                }
            }
            if (report.bodyMarkdown.isNotBlank()) {
                TextButton(onClick = onToggleExpand) {
                    Text(if (expanded) "收起完整日报" else "展开完整日报")
                }
                if (expanded) {
                    Text(
                        report.bodyMarkdown,
                        style = MaterialTheme.typography.bodySmall,
                        color = MaterialTheme.colorScheme.onSurfaceVariant,
                    )
                }
            }
        }
    }
}

private val AGENT_QUICK_COMMANDS = listOf(
    "今日日程" to "/today",
    "重点项目" to "/projects",
    "昨夜复盘简报" to "/brief",
    "今日减重与日程建议" to "结合我今天的体重和日程状态，给我一个最轻量的今日执行建议",
)

@Composable
private fun PersonalAgentQuickChatCard(
    busy: Boolean,
    reply: String?,
    isAsyncFallback: Boolean,
    onSend: (String) -> Unit,
    onDismissReply: () -> Unit,
) {
    var text by remember { mutableStateOf("") }
    Card(
        modifier = Modifier.fillMaxWidth(),
        colors = CardDefaults.cardColors(
            containerColor = MaterialTheme.colorScheme.surfaceContainerLow,
        ),
    ) {
        Column(
            modifier = Modifier.padding(14.dp),
            verticalArrangement = Arrangement.spacedBy(8.dp),
        ) {
            Row(
                verticalAlignment = Alignment.CenterVertically,
                horizontalArrangement = Arrangement.spacedBy(6.dp),
            ) {
                Icon(
                    Icons.Default.AutoAwesome,
                    contentDescription = null,
                    tint = MaterialTheme.colorScheme.primary,
                    modifier = Modifier.size(18.dp),
                )
                Text(
                    "随时对话（日程 · 项目 · 健康 · 提醒）",
                    style = MaterialTheme.typography.titleSmall,
                    fontWeight = FontWeight.SemiBold,
                )
            }
            Row(
                modifier = Modifier.fillMaxWidth(),
                verticalAlignment = Alignment.CenterVertically,
                horizontalArrangement = Arrangement.spacedBy(8.dp),
            ) {
                OutlinedTextField(
                    value = text,
                    onValueChange = { text = it },
                    placeholder = {
                        Text(
                            "说一句日程变动、项目想法或身体状态…",
                            style = MaterialTheme.typography.bodySmall,
                        )
                    },
                    singleLine = true,
                    enabled = !busy,
                    modifier = Modifier.weight(1f),
                )
                FilledTonalIconButton(
                    onClick = {
                        val trimmed = text.trim()
                        if (trimmed.isNotEmpty()) {
                            onSend(trimmed)
                            text = ""
                        }
                    },
                    enabled = !busy && text.isNotBlank(),
                ) {
                    if (busy) {
                        CircularProgressIndicator(
                            modifier = Modifier.size(18.dp),
                            strokeWidth = 2.dp,
                        )
                    } else {
                        Icon(Icons.AutoMirrored.Filled.Send, contentDescription = "发送")
                    }
                }
            }
            Row(
                modifier = Modifier
                    .fillMaxWidth()
                    .horizontalScroll(rememberScrollState()),
                horizontalArrangement = Arrangement.spacedBy(6.dp),
            ) {
                AGENT_QUICK_COMMANDS.forEach { (label, prompt) ->
                    AssistChip(
                        onClick = { if (!busy) onSend(prompt) },
                        enabled = !busy,
                        label = { Text(label) },
                    )
                }
            }
            if (!reply.isNullOrBlank()) {
                Surface(
                    shape = RoundedCornerShape(10.dp),
                    color = if (isAsyncFallback) {
                        MaterialTheme.colorScheme.tertiaryContainer.copy(alpha = 0.6f)
                    } else {
                        MaterialTheme.colorScheme.primaryContainer.copy(alpha = 0.55f)
                    },
                    modifier = Modifier.fillMaxWidth(),
                ) {
                    Column(
                        modifier = Modifier.padding(10.dp),
                        verticalArrangement = Arrangement.spacedBy(4.dp),
                    ) {
                        Row(
                            modifier = Modifier.fillMaxWidth(),
                            horizontalArrangement = Arrangement.SpaceBetween,
                            verticalAlignment = Alignment.CenterVertically,
                        ) {
                            Text(
                                text = if (isAsyncFallback) "已写入异步消息箱" else "SailTick 回复",
                                style = MaterialTheme.typography.labelMedium,
                                fontWeight = FontWeight.SemiBold,
                            )
                            IconButton(
                                onClick = onDismissReply,
                                modifier = Modifier.size(22.dp),
                            ) {
                                Icon(
                                    Icons.Default.Close,
                                    contentDescription = "关闭回复",
                                    modifier = Modifier.size(15.dp),
                                )
                            }
                        }
                        Text(reply, style = MaterialTheme.typography.bodySmall)
                    }
                }
            }
        }
    }
}
