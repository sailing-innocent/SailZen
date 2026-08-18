package com.sailzen.app.feature.project

import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.text.KeyboardOptions
import androidx.compose.foundation.verticalScroll
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.automirrored.filled.ArrowBack
import androidx.compose.material3.Button
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.Scaffold
import androidx.compose.material3.Text
import androidx.compose.material3.TopAppBar
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.collectAsState
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Modifier
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.text.input.KeyboardType
import androidx.compose.ui.unit.dp
import androidx.lifecycle.viewmodel.compose.viewModel
import com.sailzen.app.R
import com.sailzen.app.core.network.dto.MissionState

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun MissionDetailScreen(
    missionId: Int,
    onBack: () -> Unit,
    viewModel: MissionDetailViewModel = viewModel(
        factory = MissionDetailViewModelFactory(
            application = androidx.compose.ui.platform.LocalContext.current.applicationContext as android.app.Application,
            missionId = missionId,
        ),
    ),
) {
    val state by viewModel.uiState.collectAsState()

    LaunchedEffect(Unit) {
        viewModel.load()
    }

    Scaffold(
        topBar = {
            TopAppBar(
                title = { Text(stringResource(R.string.action_view_detail)) },
                navigationIcon = {
                    IconButton(onClick = onBack) {
                        Icon(Icons.AutoMirrored.Filled.ArrowBack, contentDescription = "返回")
                    }
                },
            )
        },
    ) { padding ->
        Column(
            modifier = Modifier
                .fillMaxSize()
                .padding(padding)
                .padding(16.dp)
                .verticalScroll(rememberScrollState()),
        ) {
            state.mission?.let { mission ->
                var name by remember(mission.id) { mutableStateOf(mission.name) }
                var description by remember(mission.id) { mutableStateOf(mission.description) }
                var ddl by remember(mission.id) { mutableStateOf(mission.ddl?.toString() ?: "") }

                OutlinedTextField(
                    value = name,
                    onValueChange = { name = it },
                    label = { Text(stringResource(R.string.mission_name_hint)) },
                    modifier = Modifier.fillMaxWidth(),
                    singleLine = true,
                )
                Spacer(Modifier.height(8.dp))
                OutlinedTextField(
                    value = description,
                    onValueChange = { description = it },
                    label = { Text(stringResource(R.string.mission_description_hint)) },
                    modifier = Modifier.fillMaxWidth(),
                )
                Spacer(Modifier.height(8.dp))
                OutlinedTextField(
                    value = ddl,
                    onValueChange = { ddl = it },
                    label = { Text(stringResource(R.string.mission_deadline_hint)) },
                    modifier = Modifier.fillMaxWidth(),
                    keyboardOptions = KeyboardOptions(keyboardType = KeyboardType.Number),
                    singleLine = true,
                )
                Spacer(Modifier.height(16.dp))

                Text(
                    stringResource(
                        when (mission.state) {
                            MissionState.PENDING -> R.string.mission_state_pending
                            MissionState.READY -> R.string.mission_state_ready
                            MissionState.DOING -> R.string.mission_state_doing
                            MissionState.DONE -> R.string.mission_state_done
                            MissionState.CANCELED -> R.string.mission_state_canceled
                            else -> R.string.mission_state_pending
                        }
                    ),
                    style = MaterialTheme.typography.titleMedium,
                )
                Spacer(Modifier.height(16.dp))

                Button(
                    onClick = { viewModel.updateMission(name, description, ddl) },
                    modifier = Modifier.fillMaxWidth(),
                ) { Text("保存") }

                Spacer(Modifier.height(8.dp))
                RowButtons(viewModel, mission.state)
            }
        }
    }
}

@Composable
private fun RowButtons(viewModel: MissionDetailViewModel, state: Int?) {
    val active = state != MissionState.DONE && state != MissionState.CANCELED
    Column {
        if (active && state != MissionState.DOING) {
            OutlinedButton(
                onClick = { viewModel.start() },
                modifier = Modifier.fillMaxWidth(),
            ) { Text(stringResource(R.string.action_start)) }
        }
        if (active) {
            OutlinedButton(
                onClick = { viewModel.complete() },
                modifier = Modifier.fillMaxWidth(),
            ) { Text(stringResource(R.string.action_complete)) }
            OutlinedButton(
                onClick = { viewModel.cancel() },
                modifier = Modifier.fillMaxWidth(),
            ) { Text(stringResource(R.string.action_cancel)) }
        } else {
            OutlinedButton(
                onClick = { viewModel.reopen() },
                modifier = Modifier.fillMaxWidth(),
            ) { Text(stringResource(R.string.action_reopen)) }
        }
    }
}
