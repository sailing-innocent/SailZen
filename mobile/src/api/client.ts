import axios, { AxiosInstance, AxiosError } from 'axios';
import Constants from 'expo-constants';

const API_BASE_URL =
  Constants.expoConfig?.extra?.apiBaseUrl || process.env.API_BASE_URL || 'http://localhost:8000/api/v1';
const API_TIMEOUT = parseInt(process.env.API_TIMEOUT || '10000', 10);

export class ApiClient {
  private client: AxiosInstance;

  constructor() {
    this.client = axios.create({
      baseURL: API_BASE_URL,
      timeout: API_TIMEOUT,
      headers: {
        'Content-Type': 'application/json',
      },
    });

    this.setupInterceptors();
  }

  private setupInterceptors() {
    // Request interceptor
    this.client.interceptors.request.use(
      (config) => {
        if (__DEV__) {
          console.log(`[API Request] ${config.method?.toUpperCase()} ${config.url}`);
        }
        return config;
      },
      (error) => {
        console.error('[API Request Error]', error);
        return Promise.reject(error);
      }
    );

    // Response interceptor
    this.client.interceptors.response.use(
      (response) => {
        if (__DEV__) {
          console.log(`[API Response] ${response.status} ${response.config.url}`);
        }
        return response;
      },
      (error: AxiosError) => {
        console.error('[API Error]', error.response?.status, error.message);
        return Promise.reject(error);
      }
    );
  }

  // Weight endpoints
  async getWeightList(params: { skip?: number; limit?: number; start?: number; end?: number }) {
    const response = await this.client.get('/health/weight', { params });
    return response.data;
  }

  async createWeight(data: { value: number; record_time: number }) {
    const response = await this.client.post('/health/weight', data);
    return response.data;
  }

  async getWeightStats(params: { start?: number; end?: number }) {
    const response = await this.client.get('/health/weight/avg', { params });
    return response.data;
  }

  async getWeightAnalysis(params: {
    start?: number;
    end?: number;
    model_type?: 'linear' | 'polynomial';
  }) {
    const response = await this.client.get('/health/weight/analysis', { params });
    return response.data;
  }

  // Exercise endpoints
  async getExerciseList(params: { skip?: number; limit?: number; start?: number; end?: number }) {
    const response = await this.client.get('/health/exercise', { params });
    return response.data;
  }

  async createExercise(data: {
    type: string;
    duration: number;
    calories: number;
    record_time: number;
  }) {
    const response = await this.client.post('/health/exercise', data);
    return response.data;
  }

  async updateExercise(
    id: number,
    data: { type: string; duration: number; calories: number; record_time: number }
  ) {
    const response = await this.client.put(`/health/exercise/${id}`, data);
    return response.data;
  }

  async deleteExercise(id: number) {
    const response = await this.client.delete(`/health/exercise/${id}`);
    return response.data;
  }

  // Weight Plan endpoints
  async getWeightPlan() {
    const response = await this.client.get('/health/weight/plan');
    return response.data;
  }

  async createWeightPlan(data: {
    target_weight: number;
    target_date: number;
    start_weight: number;
  }) {
    const response = await this.client.post('/health/weight/plan', data);
    return response.data;
  }

  async getWeightPlanProgress(planId?: number) {
    const response = await this.client.get('/health/weight/plan/progress', {
      params: { plan_id: planId },
    });
    return response.data;
  }

  // Retry logic for failed requests
  async retryRequest<T>(requestFn: () => Promise<T>, maxRetries = 3): Promise<T> {
    let lastError: Error | null = null;

    for (let attempt = 1; attempt <= maxRetries; attempt++) {
      try {
        return await requestFn();
      } catch (error) {
        lastError = error as Error;

        // Don't retry on 4xx errors
        if (error instanceof AxiosError && error.response?.status?.toString().startsWith('4')) {
          throw error;
        }

        if (attempt < maxRetries) {
          // Exponential backoff
          const delay = Math.min(1000 * Math.pow(2, attempt - 1), 5000);
          await new Promise((resolve) => setTimeout(resolve, delay));
        }
      }
    }

    throw lastError;
  }
}

export const apiClient = new ApiClient();
