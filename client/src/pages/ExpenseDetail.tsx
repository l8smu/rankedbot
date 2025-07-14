import React from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { useRoute } from 'wouter';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Textarea } from '@/components/ui/input';
import { CheckCircle, XCircle, Clock, ArrowLeft, User, Calendar, DollarSign, Tag } from 'lucide-react';
import { Link } from 'wouter';
import { Expense, User as UserType } from '../../../shared/schema';
import { apiRequest } from '@/lib/queryClient';
import { useToast } from '@/hooks/use-toast';

const ExpenseDetail: React.FC = () => {
  const [, params] = useRoute('/expenses/:id');
  const { toast } = useToast();
  const queryClient = useQueryClient();
  const expenseId = params?.id;
  
  const [rejectionReason, setRejectionReason] = React.useState('');
  const [showRejectForm, setShowRejectForm] = React.useState(false);

  const { data: expense, isLoading } = useQuery<Expense>({
    queryKey: ['/api/expenses', expenseId],
    enabled: !!expenseId,
  });

  const { data: users } = useQuery<UserType[]>({
    queryKey: ['/api/users'],
  });

  const approveMutation = useMutation({
    mutationFn: ({ expenseId, approverId }: { expenseId: string; approverId: string }) =>
      apiRequest(`/api/expenses/${expenseId}/approve`, {
        method: 'POST',
        body: JSON.stringify({ approverId }),
      }),
    onSuccess: () => {
      toast({
        title: 'Success',
        description: 'Expense approved successfully',
        variant: 'success',
      });
      queryClient.invalidateQueries({ queryKey: ['/api/expenses'] });
      queryClient.invalidateQueries({ queryKey: ['/api/dashboard/stats'] });
    },
    onError: () => {
      toast({
        title: 'Error',
        description: 'Failed to approve expense',
        variant: 'error',
      });
    },
  });

  const rejectMutation = useMutation({
    mutationFn: ({ expenseId, approverId, reason }: { expenseId: string; approverId: string; reason: string }) =>
      apiRequest(`/api/expenses/${expenseId}/reject`, {
        method: 'POST',
        body: JSON.stringify({ approverId, reason }),
      }),
    onSuccess: () => {
      toast({
        title: 'Success',
        description: 'Expense rejected successfully',
        variant: 'success',
      });
      queryClient.invalidateQueries({ queryKey: ['/api/expenses'] });
      queryClient.invalidateQueries({ queryKey: ['/api/dashboard/stats'] });
      setShowRejectForm(false);
      setRejectionReason('');
    },
    onError: () => {
      toast({
        title: 'Error',
        description: 'Failed to reject expense',
        variant: 'error',
      });
    },
  });

  const handleApprove = () => {
    if (!expenseId) return;
    approveMutation.mutate({ expenseId, approverId: 'user-2' }); // Demo: using manager ID
  };

  const handleReject = () => {
    if (!expenseId || !rejectionReason.trim()) return;
    rejectMutation.mutate({ expenseId, approverId: 'user-2', reason: rejectionReason });
  };

  if (isLoading) {
    return (
      <div className="p-6">
        <div className="animate-pulse">
          <div className="h-8 bg-gray-200 dark:bg-gray-700 rounded mb-6"></div>
          <div className="space-y-4">
            <div className="h-40 bg-gray-200 dark:bg-gray-700 rounded-lg"></div>
            <div className="h-32 bg-gray-200 dark:bg-gray-700 rounded-lg"></div>
          </div>
        </div>
      </div>
    );
  }

  if (!expense) {
    return (
      <div className="p-6">
        <div className="text-center py-8">
          <p className="text-gray-500 dark:text-gray-400">Expense not found</p>
          <Link href="/expenses">
            <Button className="mt-4">
              Back to Expenses
            </Button>
          </Link>
        </div>
      </div>
    );
  }

  const user = users?.find(u => u.id === expense.userId);
  const approver = expense.approvedBy ? users?.find(u => u.id === expense.approvedBy) : null;

  const formatCurrency = (amount: number) => {
    return new Intl.NumberFormat('en-US', {
      style: 'currency',
      currency: 'USD',
    }).format(amount);
  };

  const formatDate = (dateString: string) => {
    return new Date(dateString).toLocaleDateString('en-US', {
      year: 'numeric',
      month: 'long',
      day: 'numeric',
      hour: '2-digit',
      minute: '2-digit',
    });
  };

  const getStatusColor = (status: string) => {
    switch (status) {
      case 'approved':
        return 'text-green-600 dark:text-green-400';
      case 'rejected':
        return 'text-red-600 dark:text-red-400';
      case 'pending':
        return 'text-yellow-600 dark:text-yellow-400';
      default:
        return 'text-gray-600 dark:text-gray-400';
    }
  };

  const getStatusIcon = (status: string) => {
    switch (status) {
      case 'approved':
        return <CheckCircle className="h-5 w-5 text-green-600 dark:text-green-400" />;
      case 'rejected':
        return <XCircle className="h-5 w-5 text-red-600 dark:text-red-400" />;
      case 'pending':
        return <Clock className="h-5 w-5 text-yellow-600 dark:text-yellow-400" />;
      default:
        return <Clock className="h-5 w-5 text-gray-600 dark:text-gray-400" />;
    }
  };

  return (
    <div className="p-6">
      <div className="max-w-4xl mx-auto">
        <div className="flex items-center gap-4 mb-6">
          <Link href="/expenses">
            <Button variant="outline" size="sm">
              <ArrowLeft className="h-4 w-4 mr-2" />
              Back to Expenses
            </Button>
          </Link>
          <h1 className="text-3xl font-bold text-gray-900 dark:text-gray-100">
            Expense Details
          </h1>
        </div>

        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
          {/* Main Expense Info */}
          <Card>
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                {getStatusIcon(expense.status)}
                {expense.title}
              </CardTitle>
            </CardHeader>
            <CardContent className="space-y-4">
              <div className="flex items-center gap-3">
                <User className="h-5 w-5 text-gray-400" />
                <div>
                  <p className="font-medium text-gray-900 dark:text-gray-100">
                    {user?.name || 'Unknown User'}
                  </p>
                  <p className="text-sm text-gray-500 dark:text-gray-400">
                    {user?.email}
                  </p>
                </div>
              </div>

              <div className="flex items-center gap-3">
                <DollarSign className="h-5 w-5 text-gray-400" />
                <div>
                  <p className="font-medium text-gray-900 dark:text-gray-100">
                    {formatCurrency(expense.amount)}
                  </p>
                  <p className="text-sm text-gray-500 dark:text-gray-400">
                    Amount
                  </p>
                </div>
              </div>

              <div className="flex items-center gap-3">
                <Tag className="h-5 w-5 text-gray-400" />
                <div>
                  <p className="font-medium text-gray-900 dark:text-gray-100 capitalize">
                    {expense.category}
                  </p>
                  <p className="text-sm text-gray-500 dark:text-gray-400">
                    Category
                  </p>
                </div>
              </div>

              <div className="flex items-center gap-3">
                <Calendar className="h-5 w-5 text-gray-400" />
                <div>
                  <p className="font-medium text-gray-900 dark:text-gray-100">
                    {formatDate(expense.submittedAt)}
                  </p>
                  <p className="text-sm text-gray-500 dark:text-gray-400">
                    Submitted
                  </p>
                </div>
              </div>

              <div className="pt-4">
                <h4 className="font-medium text-gray-900 dark:text-gray-100 mb-2">
                  Description
                </h4>
                <p className="text-gray-700 dark:text-gray-300">
                  {expense.description}
                </p>
              </div>
            </CardContent>
          </Card>

          {/* Status and Actions */}
          <Card>
            <CardHeader>
              <CardTitle>Status & Actions</CardTitle>
            </CardHeader>
            <CardContent className="space-y-4">
              <div className="flex items-center gap-3">
                {getStatusIcon(expense.status)}
                <div>
                  <p className={`font-medium capitalize ${getStatusColor(expense.status)}`}>
                    {expense.status}
                  </p>
                  <p className="text-sm text-gray-500 dark:text-gray-400">
                    Current Status
                  </p>
                </div>
              </div>

              {expense.approvedAt && (
                <div className="p-3 bg-green-50 dark:bg-green-900/20 rounded-lg">
                  <p className="font-medium text-green-900 dark:text-green-100">
                    Approved
                  </p>
                  <p className="text-sm text-green-700 dark:text-green-300">
                    By {approver?.name || 'Unknown'} on {formatDate(expense.approvedAt)}
                  </p>
                </div>
              )}

              {expense.rejectedAt && (
                <div className="p-3 bg-red-50 dark:bg-red-900/20 rounded-lg">
                  <p className="font-medium text-red-900 dark:text-red-100">
                    Rejected
                  </p>
                  <p className="text-sm text-red-700 dark:text-red-300">
                    By {users?.find(u => u.id === expense.rejectedBy)?.name || 'Unknown'} on {formatDate(expense.rejectedAt)}
                  </p>
                  {expense.rejectionReason && (
                    <p className="text-sm text-red-700 dark:text-red-300 mt-2">
                      Reason: {expense.rejectionReason}
                    </p>
                  )}
                </div>
              )}

              {expense.status === 'pending' && (
                <div className="space-y-3 pt-4">
                  <h4 className="font-medium text-gray-900 dark:text-gray-100">
                    Manager Actions
                  </h4>
                  
                  {!showRejectForm ? (
                    <div className="flex gap-3">
                      <Button
                        onClick={handleApprove}
                        disabled={approveMutation.isPending}
                        className="flex-1"
                      >
                        {approveMutation.isPending ? 'Approving...' : 'Approve'}
                      </Button>
                      <Button
                        variant="outline"
                        onClick={() => setShowRejectForm(true)}
                        className="flex-1"
                      >
                        Reject
                      </Button>
                    </div>
                  ) : (
                    <div className="space-y-3">
                      <Textarea
                        value={rejectionReason}
                        onChange={(e) => setRejectionReason(e.target.value)}
                        placeholder="Enter rejection reason..."
                        rows={3}
                      />
                      <div className="flex gap-3">
                        <Button
                          onClick={handleReject}
                          disabled={rejectMutation.isPending || !rejectionReason.trim()}
                          variant="outline"
                          className="flex-1"
                        >
                          {rejectMutation.isPending ? 'Rejecting...' : 'Confirm Rejection'}
                        </Button>
                        <Button
                          onClick={() => {
                            setShowRejectForm(false);
                            setRejectionReason('');
                          }}
                          variant="ghost"
                          className="flex-1"
                        >
                          Cancel
                        </Button>
                      </div>
                    </div>
                  )}
                </div>
              )}
            </CardContent>
          </Card>
        </div>
      </div>
    </div>
  );
};

export default ExpenseDetail;