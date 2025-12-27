import { apiClient } from './api';

export type QAFlag = {
  passed: boolean;
  [key: string]: unknown;
};

export type QAFlags = Record<string, QAFlag>;

export interface QueueItem {
  test_id: string;
  sample_id: string;
  project_id: string;
  project_name: string;
  parameter: string;
  value: string;
  unit: string;
  method: string;
  tested_at: string;
  certificate_file?: string;
  sample_type: string;
  sample_collected_at: string;
  qa_flags: QAFlags | null;
  risk_score: number;
  uploaded_by: string;
}

export interface QueueResponse {
  queue: QueueItem[];
  total_pending: number;
  high_risk_count: number;
}

export interface ReviewRequest {
  action: 'approve' | 'reject';
  reviewer_id: string;
  comments?: string;
}

export interface ReviewResponse {
  test_id: string;
  action: string;
  reviewer_id: string;
  sample_status: string;
  test_passed: boolean;
}

export const mrvApi = {
  // Get review queue
  getQueue: async (): Promise<QueueResponse> => {
    const response = await apiClient.get<QueueResponse>('/api/mrv/queue');
    return response.data;
  },

  // Review a test
  reviewTest: async (testId: string, reviewData: ReviewRequest): Promise<ReviewResponse> => {
    const formData = new FormData();
    formData.append('action', reviewData.action);
    formData.append('reviewer_id', reviewData.reviewer_id);
    if (reviewData.comments) {
      formData.append('comments', reviewData.comments);
    }

    const response = await apiClient.post<ReviewResponse>(
      `/api/mrv/tests/${testId}/review`,
      formData,
      {
        headers: {
          'Content-Type': 'multipart/form-data',
        },
      }
    );
    return response.data;
  },

  // Get sample details
  getSampleDetail: async (sampleId: string) => {
    const response = await apiClient.get(`/api/mrv/samples/${sampleId}`);
    return response.data;
  },

  // Get test details
  getTestDetail: async (testId: string) => {
    const response = await apiClient.get(`/api/mrv/tests/${testId}`);
    return response.data;
  },

  // Upload test result
  uploadTestResult: async (sampleId: string, testData: FormData) => {
    const response = await apiClient.post(`/api/mrv/tests/${sampleId}/upload`, testData, {
      headers: {
        'Content-Type': 'multipart/form-data',
      },
    });
    return response.data;
  },

  // Submit sample to lab
  submitToLab: async (sampleId: string, labData: FormData) => {
    const response = await apiClient.post(`/api/mrv/samples/${sampleId}/submit_lab`, labData, {
      headers: {
        'Content-Type': 'multipart/form-data',
      },
    });
    return response.data;
  },

  // Add chain step
  addChainStep: async (sampleId: string, stepData: FormData) => {
    const response = await apiClient.post(`/api/mrv/samples/${sampleId}/chain`, stepData, {
      headers: {
        'Content-Type': 'multipart/form-data',
      },
    });
    return response.data;
  },

  // Create sample
  createSample: async (sampleData: FormData) => {
    const response = await apiClient.post('/api/mrv/samples', sampleData, {
      headers: {
        'Content-Type': 'multipart/form-data',
      },
    });
    return response.data;
  },

  // Get MRV stats
  getStats: async () => {
    const response = await apiClient.get('/api/mrv/stats');
    return response.data;
  },
};
