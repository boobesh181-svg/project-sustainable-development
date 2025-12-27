import React, { useState, useEffect } from 'react';
import { toast } from 'react-hot-toast';
import { format } from 'date-fns';
import { apiClient } from '../../services/api';
import { useAuth } from '../../hooks/useAuth';

type QAFlag = {
  passed: boolean;
  [key: string]: unknown;
};

type QAFlags = Record<string, QAFlag>;

function isQAFlag(flag: unknown): flag is QAFlag {
  if (typeof flag !== 'object' || flag === null) return false;
  return typeof (flag as { passed?: unknown }).passed === 'boolean';
}

interface QueueItem {
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

interface QueueResponse {
  queue: QueueItem[];
  total_pending: number;
  high_risk_count: number;
}

const MRVQueuePage: React.FC = () => {
  const [queue, setQueue] = useState<QueueItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [selectedTest, setSelectedTest] = useState<QueueItem | null>(null);
  const [showReviewModal, setShowReviewModal] = useState(false);
  const [stats, setStats] = useState({ total: 0, highRisk: 0 });

  useEffect(() => {
    fetchQueue();
  }, []);

  const fetchQueue = async () => {
    try {
      setLoading(true);
      const response = await apiClient.get<QueueResponse>('/api/mrv/queue');
      setQueue(response.data.queue);
      setStats({
        total: response.data.total_pending,
        highRisk: response.data.high_risk_count
      });
    } catch {
      toast.error('Failed to fetch review queue');
    } finally {
      setLoading(false);
    }
  };

  const handleReview = (test: QueueItem) => {
    setSelectedTest(test);
    setShowReviewModal(true);
  };

  const handleCertificateClick = (certificatePath: string) => {
    // Open certificate in new tab or modal
    window.open(`/api/files/${certificatePath}`, '_blank');
  };

  const getRiskBadgeColor = (riskScore: number) => {
    if (riskScore >= 10) return 'bg-red-100 text-red-800 border-red-200';
    if (riskScore >= 5) return 'bg-orange-100 text-orange-800 border-orange-200';
    if (riskScore >= 2) return 'bg-yellow-100 text-yellow-800 border-yellow-200';
    return 'bg-green-100 text-green-800 border-green-200';
  };

  const getRiskLabel = (riskScore: number) => {
    if (riskScore >= 10) return 'Critical';
    if (riskScore >= 5) return 'High';
    if (riskScore >= 2) return 'Medium';
    return 'Low';
  };

  const getQAFlagColor = (flag: QAFlag | null | undefined) => {
    if (!flag) return 'bg-gray-100 text-gray-800';
    return flag.passed ? 'bg-green-100 text-green-800' : 'bg-red-100 text-red-800';
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-blue-600"></div>
      </div>
    );
  }

  return (
    <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
      {/* Header */}
      <div className="mb-8">
        <h1 className="text-2xl font-bold text-gray-900">MRV Review Queue</h1>
        <p className="text-gray-600 mt-2">
          Review and approve/reject MRV test results
        </p>
      </div>

      {/* Stats Cards */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4 mb-8">
        <div className="bg-white rounded-lg shadow p-6">
          <div className="flex items-center">
            <div className="flex-1">
              <p className="text-sm font-medium text-gray-600">Total Pending</p>
              <p className="text-2xl font-bold text-gray-900">{stats.total}</p>
            </div>
            <div className="bg-blue-100 rounded-full p-3">
              <svg className="w-6 h-6 text-blue-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z" />
              </svg>
            </div>
          </div>
        </div>

        <div className="bg-white rounded-lg shadow p-6">
          <div className="flex items-center">
            <div className="flex-1">
              <p className="text-sm font-medium text-gray-600">High Risk</p>
              <p className="text-2xl font-bold text-red-600">{stats.highRisk}</p>
            </div>
            <div className="bg-red-100 rounded-full p-3">
              <svg className="w-6 h-6 text-red-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-2.5L13.732 4c-.77-.833-1.964-.833-2.732 0L4.082 15.5c-.77.833.192 2.5 1.732 2.5z" />
              </svg>
            </div>
          </div>
        </div>

        <div className="bg-white rounded-lg shadow p-6">
          <div className="flex items-center">
            <div className="flex-1">
              <p className="text-sm font-medium text-gray-600">Avg Risk Score</p>
              <p className="text-2xl font-bold text-gray-900">
                {queue.length > 0 ? (queue.reduce((sum, item) => sum + item.risk_score, 0) / queue.length).toFixed(1) : '0'}
              </p>
            </div>
            <div className="bg-yellow-100 rounded-full p-3">
              <svg className="w-6 h-6 text-yellow-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 10V3L4 14h7v7l9-11h-7z" />
              </svg>
            </div>
          </div>
        </div>
      </div>

      {/* Queue Table */}
      <div className="bg-white shadow rounded-lg overflow-hidden">
        <div className="px-6 py-4 border-b border-gray-200">
          <h2 className="text-lg font-medium text-gray-900">Pending Reviews</h2>
        </div>
        
        {queue.length === 0 ? (
          <div className="text-center py-12">
            <svg className="mx-auto h-12 w-12 text-gray-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z" />
            </svg>
            <h3 className="mt-2 text-sm font-medium text-gray-900">No pending reviews</h3>
            <p className="mt-1 text-sm text-gray-500">All MRV tests have been reviewed.</p>
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="min-w-full divide-y divide-gray-200">
              <thead className="bg-gray-50">
                <tr>
                  <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                    Risk
                  </th>
                  <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                    Sample / Project
                  </th>
                  <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                    Test Details
                  </th>
                  <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                    QA Flags
                  </th>
                  <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                    Certificate
                  </th>
                  <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                    Actions
                  </th>
                </tr>
              </thead>
              <tbody className="bg-white divide-y divide-gray-200">
                {queue.map((item) => (
                  <tr key={item.test_id} className="hover:bg-gray-50">
                    <td className="px-6 py-4 whitespace-nowrap">
                      <span className={`inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium border ${getRiskBadgeColor(item.risk_score)}`}>
                        {getRiskLabel(item.risk_score)}
                      </span>
                    </td>
                    <td className="px-6 py-4 whitespace-nowrap">
                      <div>
                        <div className="text-sm font-medium text-gray-900">{item.sample_id}</div>
                        <div className="text-sm text-gray-500">{item.project_name}</div>
                        <div className="text-xs text-gray-400">{item.sample_type}</div>
                      </div>
                    </td>
                    <td className="px-6 py-4 whitespace-nowrap">
                      <div>
                        <div className="text-sm font-medium text-gray-900">{item.parameter}</div>
                        <div className="text-sm text-gray-500">{item.value} {item.unit}</div>
                        <div className="text-xs text-gray-400">{item.method}</div>
                        <div className="text-xs text-gray-400">
                          {format(new Date(item.tested_at), 'MMM d, yyyy')}
                        </div>
                      </div>
                    </td>
                    <td className="px-6 py-4 whitespace-nowrap">
                      <div className="flex flex-wrap gap-1">
                        {item.qa_flags && Object.entries(item.qa_flags).map(([key, flag]: [string, unknown]) => {
                          if (key.endsWith('_flag') && isQAFlag(flag)) {
                            return (
                              <span
                                key={key}
                                className={`inline-flex items-center px-2 py-0.5 rounded text-xs font-medium ${getQAFlagColor(flag)}`}
                              >
                                {key.replace('_flag', '')}
                              </span>
                            );
                          }
                          return null;
                        })}
                      </div>
                    </td>
                    <td className="px-6 py-4 whitespace-nowrap">
                      {item.certificate_file ? (
                        <button
                          onClick={() => handleCertificateClick(item.certificate_file!)}
                          className="text-blue-600 hover:text-blue-900 text-sm font-medium"
                        >
                          View Certificate
                        </button>
                      ) : (
                        <span className="text-gray-400 text-sm">No certificate</span>
                      )}
                    </td>
                    <td className="px-6 py-4 whitespace-nowrap text-sm font-medium">
                      <button
                        onClick={() => handleReview(item)}
                        className="bg-blue-600 text-white px-3 py-1 rounded-md text-sm hover:bg-blue-700 focus:outline-none focus:ring-2 focus:ring-blue-500"
                      >
                        Review
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>

      {/* Review Modal */}
      {showReviewModal && selectedTest && (
        <MRVReviewModal
          test={selectedTest}
          isOpen={showReviewModal}
          onClose={() => {
            setShowReviewModal(false);
            setSelectedTest(null);
          }}
          onReviewComplete={() => {
            fetchQueue(); // Refresh queue after review
            setShowReviewModal(false);
            setSelectedTest(null);
          }}
        />
      )}
    </div>
  );
};

// Review Modal Component
interface MRVReviewModalProps {
  test: QueueItem;
  isOpen: boolean;
  onClose: () => void;
  onReviewComplete: () => void;
}

const MRVReviewModal: React.FC<MRVReviewModalProps> = ({
  test,
  isOpen,
  onClose,
  onReviewComplete
}) => {
  const { user } = useAuth();
  const [loading, setLoading] = useState(false);
  const [comments, setComments] = useState('');
  const [action, setAction] = useState<'approve' | 'reject'>('approve');

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    
    if (!user) {
      toast.error('User not authenticated');
      return;
    }

    setLoading(true);
    try {
      const formData = new FormData();
      formData.append('action', action);
      formData.append('reviewer_id', user.id);
      if (comments) {
        formData.append('comments', comments);
      }

      await apiClient.post(`/api/mrv/tests/${test.test_id}/review`, formData, {
        headers: {
          'Content-Type': 'multipart/form-data',
        },
      });

      toast.success(`Test ${action}d successfully`);
      onReviewComplete();
    } catch {
      toast.error(`Failed to ${action} test`);
    } finally {
      setLoading(false);
    }
  };

  if (!isOpen) return null;

  return (
    <div className="fixed inset-0 bg-gray-600 bg-opacity-50 overflow-y-auto h-full w-full z-50">
      <div className="relative top-20 mx-auto p-5 border w-11/12 md:w-3/4 lg:w-1/2 shadow-lg rounded-lg bg-white">
        <div className="flex justify-between items-center mb-4">
          <h3 className="text-lg font-bold text-gray-900">Review MRV Test</h3>
          <button
            onClick={onClose}
            className="text-gray-400 hover:text-gray-600"
          >
            <svg className="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
            </svg>
          </button>
        </div>

        {/* Test Details */}
        <div className="mb-6 p-4 bg-gray-50 rounded-lg">
          <h4 className="font-medium text-gray-900 mb-2">Test Details</h4>
          <div className="grid grid-cols-2 gap-4 text-sm">
            <div>
              <span className="font-medium">Sample ID:</span> {test.sample_id}
            </div>
            <div>
              <span className="font-medium">Project:</span> {test.project_name}
            </div>
            <div>
              <span className="font-medium">Parameter:</span> {test.parameter}
            </div>
            <div>
              <span className="font-medium">Result:</span> {test.value} {test.unit}
            </div>
            <div>
              <span className="font-medium">Method:</span> {test.method}
            </div>
            <div>
              <span className="font-medium">Tested:</span> {format(new Date(test.tested_at), 'MMM d, yyyy')}
            </div>
          </div>
        </div>

        {/* Certificate Preview */}
        {test.certificate_file && (
          <div className="mb-6">
            <h4 className="font-medium text-gray-900 mb-2">Certificate</h4>
            <div className="border rounded-lg p-4 bg-gray-50">
              <a
                href={`/api/files/${test.certificate_file}`}
                target="_blank"
                rel="noopener noreferrer"
                className="text-blue-600 hover:text-blue-800 underline"
              >
                Open Certificate in New Tab
              </a>
            </div>
          </div>
        )}

        {/* QA Flags */}
        {test.qa_flags && (
          <div className="mb-6">
            <h4 className="font-medium text-gray-900 mb-2">QA Flags</h4>
            <div className="space-y-2">
              {Object.entries(test.qa_flags).map(([key, flag]: [string, unknown]) => {
                if (key.endsWith('_flag') && isQAFlag(flag)) {
                  return (
                    <div key={key} className="flex items-center justify-between p-2 bg-gray-50 rounded">
                      <span className="text-sm font-medium">{key.replace('_flag', '')}</span>
                      <span className={`px-2 py-1 rounded text-xs ${flag.passed ? 'bg-green-100 text-green-800' : 'bg-red-100 text-red-800'}`}>
                        {flag.passed ? 'Passed' : 'Failed'}
                      </span>
                    </div>
                  );
                }
                return null;
              })}
            </div>
          </div>
        )}

        {/* Review Form */}
        <form onSubmit={handleSubmit} className="space-y-4">
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-2">
              Review Action
            </label>
            <div className="flex space-x-4">
              <label className="flex items-center">
                <input
                  type="radio"
                  value="approve"
                  checked={action === 'approve'}
                  onChange={(e) => setAction(e.target.value as 'approve' | 'reject')}
                  className="mr-2"
                />
                <span className="text-green-600 font-medium">Approve</span>
              </label>
              <label className="flex items-center">
                <input
                  type="radio"
                  value="reject"
                  checked={action === 'reject'}
                  onChange={(e) => setAction(e.target.value as 'approve' | 'reject')}
                  className="mr-2"
                />
                <span className="text-red-600 font-medium">Reject</span>
              </label>
            </div>
          </div>

          <div>
            <label className="block text-sm font-medium text-gray-700 mb-2">
              Comments (optional)
            </label>
            <textarea
              value={comments}
              onChange={(e) => setComments(e.target.value)}
              rows={4}
              className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
              placeholder="Add any comments about this review..."
            />
          </div>

          <div className="flex justify-end space-x-3 pt-4 border-t">
            <button
              type="button"
              onClick={onClose}
              className="px-4 py-2 border border-gray-300 rounded-md text-gray-700 hover:bg-gray-50 focus:outline-none focus:ring-2 focus:ring-blue-500"
            >
              Cancel
            </button>
            <button
              type="submit"
              disabled={loading}
              className={`px-4 py-2 rounded-md text-white focus:outline-none focus:ring-2 focus:ring-blue-500 disabled:opacity-50 ${
                action === 'approve' 
                  ? 'bg-green-600 hover:bg-green-700' 
                  : 'bg-red-600 hover:bg-red-700'
              }`}
            >
              {loading ? 'Processing...' : `${action.charAt(0).toUpperCase() + action.slice(1)} Test`}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
};

export default MRVQueuePage;
