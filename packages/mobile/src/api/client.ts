import axios, { AxiosInstance, AxiosError } from 'axios';
import { Platform } from 'react-native';

// Determine the correct API base URL based on platform and environment
const getApiBaseUrl = (): string => {
  // In development, use the environment variable
  if (__DEV__) {
    // For Android emulator, 10.0.2.2 maps to host's localhost
    // For iOS simulator, localhost works directly
    // For physical device, use your computer's actual IP address
    return process.env.API_BASE_URL || 'http://10.0.2.2:4399/api/v1';
  }
  
  // In production, use the production API
  return process.env.API_BASE_URL || 'https://api.sailzen.example.com/api/v1';
};

const API_BASE_URL = getApiBaseUrl();
const API_TIMEOUT = parseInt(process.env.API_TIMEOUT || '10000', 10);

console.log(`[API] Using base URL: ${API_BASE_URL}`);

export interface WeightRecord {
  id: number;
  value: number;
  record_time: number;
  created_at: number;
  updated_at: number;
}

export interface ExerciseRecord {
  id: number;
  type: 'running' | 'swimming' | 'cycling' | 'fitness' | 'yoga' | 'other';
  duration: number;
  calories: number;
  record_time: number;
  created_at: number;
  updated_at: number;
}

export interface WeightPlan {
  id: number;
  target_weight: number;
  target_date: number;
  start_weight: number;
  start_date: number;
  created_at: number;
  updated_at: number;
}

export interface WeightStats {
  avg: number;
  min: number;
  max: number;
  count: number;
}

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
          console.log(`[API Request] ${config.method?.toUpperCase()} ${config.url}`, config.params || '');
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
        if (error.code === 'ECONNREFUSED') {
          console.error('[API Error] Connection refused. Please check:');
          console.error('  1. Backend server is running (python server.py)');
          console.error('  2. Correct IP address is configured in .env.development');
          console.error(`  3. Current URL: ${API_BASE_URL}`);
        } else {
          console.error('[API Error]', error.response?.status, error.message);
        }
        return Promise.reject(error);
      }
    );
  }

  // ==================== Weight APIs ====================
  
  async getWeightList(params: { skip?: number; limit?: number; start?: number; end?: number } = {}): Promise<WeightRecord[]> {
    const response = await this.client.get('/health/weight', { params });
    return response.data;
  }

  async createWeight(data: { value: number; record_time: number }): Promise<WeightRecord> {
    const response = await this.client.post('/health/weight', data);
    return response.data;
  }

  async getWeightStats(params: { start?: number; end?: number } = {}): Promise<WeightStats> {
    const response = await this.client.get('/health/weight/avg', { params });
    return response.data;
  }

  async getWeightAnalysis(params: {
    start?: number;
    end?: number;
    model_type?: 'linear' | 'polynomial';
  } = {}): Promise<any> {
    const response = await this.client.get('/health/weight/analysis', { params });
    return response.data;
  }

  // ==================== Exercise APIs ====================
  
  async getExerciseList(params: { skip?: number; limit?: number; start?: number; end?: number } = {}): Promise<ExerciseRecord[]> {
    const response = await this.client.get('/health/exercise', { params });
    return response.data;
  }

  async createExercise(data: {
    type: string;
    duration: number;
    calories: number;
    record_time: number;
  }): Promise<ExerciseRecord> {
    const response = await this.client.post('/health/exercise', data);
    return response.data;
  }

  async updateExercise(
    id: number,
    data: { type: string; duration: number; calories: number; record_time: number }
  ): Promise<ExerciseRecord> {
    const response = await this.client.put(`/health/exercise/${id}`, data);
    return response.data;
  }

  async deleteExercise(id: number): Promise<void> {
    const response = await this.client.delete(`/health/exercise/${id}`);
    return response.data;
  }

  // ==================== Weight Plan APIs ====================
  
  async getWeightPlan(): Promise<WeightPlan | null> {
    try {
      const response = await this.client.get('/health/weight/plan');
      // Check if valid plan (has positive id)
      if (!response.data || response.data.id === -1) {
        return null;
      }
      return response.data;
    } catch (error: any) {
      if (error.response?.status === 404) {
        return null;
      }
      throw error;
    }
  }

  async createWeightPlan(data: {
    target_weight: number;
    target_date: number;
    start_weight: number;
  }): Promise<WeightPlan> {
    const response = await this.client.post('/health/weight/plan', data);
    return response.data;
  }

  async getWeightPlanProgress(planId?: number): Promise<any> {
    const response = await this.client.get('/health/weight/plan/progress', {
      params: planId ? { plan_id: planId } : {},
    });
    return response.data;
  }

  // ==================== Utility Methods ====================

  /**
   * Check if the API is reachable
   */
  async healthCheck(): Promise<boolean> {
    try {
      await this.client.get('/health/weight', { params: { limit: 1 } });
      return true;
    } catch (error) {
      return false;
    }
  }

  /**
   * Retry logic for failed requests
   */
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
          console.log(`[API] Retry attempt ${attempt}/${maxRetries} after ${delay}ms`);
          await new Promise((resolve) => setTimeout(resolve, delay));
        }
      }
    }

    throw lastError;
  }
}

export const apiClient = new ApiClient();
