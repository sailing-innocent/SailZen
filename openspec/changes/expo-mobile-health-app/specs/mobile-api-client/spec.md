## ADDED Requirements

### Requirement: API client initialization
The app SHALL have a configured API client for backend communication.

#### Scenario: Client configuration
- **WHEN** the app initializes
- **THEN** an API client is created with:
  - baseURL from environment config (dev/prod)
  - default timeout (10s)
  - request/response interceptors

### Requirement: Weight API endpoints
The API client SHALL support all weight-related endpoints.

#### Scenario: Get weight list
- **WHEN** calling `api.getWeightList({ skip, limit, start, end })`
- **THEN** a GET request is made to `/api/v1/health/weight`
- **AND** returns array of WeightRecord objects

#### Scenario: Create weight
- **WHEN** calling `api.createWeight({ value, record_time })`
- **THEN** a POST request is made to `/api/v1/health/weight`
- **AND** returns the created WeightRecord with server_id

#### Scenario: Get weight statistics
- **WHEN** calling `api.getWeightStats({ start, end })`
- **THEN** a GET request is made to `/api/v1/health/weight/avg`
- **AND** returns statistics object

#### Scenario: Get weight trend analysis
- **WHEN** calling `api.getWeightAnalysis({ start, end, model_type })`
- **THEN** a GET request is made to `/api/v1/health/weight/analysis`
- **AND** returns trend data including slope and predictions

### Requirement: Exercise API endpoints
The API client SHALL support all exercise-related endpoints.

#### Scenario: Get exercise list
- **WHEN** calling `api.getExerciseList({ skip, limit, start, end })`
- **THEN** a GET request is made to `/api/v1/health/exercise`
- **AND** returns array of ExerciseRecord objects

#### Scenario: Create exercise
- **WHEN** calling `api.createExercise({ type, duration, calories, record_time })`
- **THEN** a POST request is made to `/api/v1/health/exercise`
- **AND** returns the created ExerciseRecord with server_id

#### Scenario: Update exercise
- **WHEN** calling `api.updateExercise(id, data)`
- **THEN** a PUT request is made to `/api/v1/health/exercise/{id}`
- **AND** returns the updated ExerciseRecord

#### Scenario: Delete exercise
- **WHEN** calling `api.deleteExercise(id)`
- **THEN** a DELETE request is made to `/api/v1/health/exercise/{id}`
- **AND** returns success status

### Requirement: Weight plan API endpoints
The API client SHALL support weight plan endpoints.

#### Scenario: Get active weight plan
- **WHEN** calling `api.getWeightPlan()`
- **THEN** a GET request is made to `/api/v1/health/weight/plan`
- **AND** returns WeightPlan object or null

#### Scenario: Create weight plan
- **WHEN** calling `api.createWeightPlan({ target_weight, target_date, start_weight })`
- **THEN** a POST request is made to `/api/v1/health/weight/plan`
- **AND** returns the created WeightPlan

#### Scenario: Get weight plan progress
- **WHEN** calling `api.getWeightPlanProgress({ plan_id })`
- **THEN** a GET request is made to `/api/v1/health/weight/plan/progress`
- **AND** returns progress data with control rate

### Requirement: Error handling
The API client SHALL handle HTTP errors and network failures.

#### Scenario: 4xx error handling
- **WHEN** the server returns 4xx error
- **THEN** the error is parsed and thrown with message
- **AND** the specific error type is preserved

#### Scenario: 5xx error handling
- **WHEN** the server returns 5xx error
- **THEN** a generic server error is thrown
- **AND** retry logic can be applied

#### Scenario: Network timeout
- **WHEN** request exceeds timeout duration
- **THEN** a timeout error is thrown
- **AND** the request can be retried

### Requirement: Request/Response logging
The API client SHALL support debug logging in development mode.

#### Scenario: Debug logging
- **WHEN** `__DEV__` is true
- **AND** API_DEBUG environment variable is set
- **THEN** all requests and responses are logged to console
- **AND** sensitive data is redacted

