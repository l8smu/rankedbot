import React, { useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Select, SelectItem } from '@/components/ui/input';
import { Link } from 'wouter';
import { Plus, Search, Download, Filter } from 'lucide-react';
import { Expense, User, ExpenseCategory, ExpenseStatus } from '../../../shared/schema';

const ExpensesList: React.FC = () => {
  const [searchTerm, setSearchTerm] = useState('');
  const [statusFilter, setStatusFilter] = useState('all');
  const [categoryFilter, setCategoryFilter] = useState('all');

  const { data: expenses, isLoading } = useQuery<Expense[]>({
    queryKey: ['/api/expenses'],
  });

  const { data: users } = useQuery<User[]>({
    queryKey: ['/api/users'],
  });

  const handleExport = async (format: 'json' | 'csv') => {
    const startDate = new Date(Date.now() - 30 * 24 * 60 * 60 * 1000).toISOString().split('T')[0];
    const endDate = new Date().toISOString().split('T')[0];
    
    const url = `/api/export/expenses?startDate=${startDate}&endDate=${endDate}&format=${format}`;
    
    if (format === 'csv') {
      const response = await fetch(url);
      const blob = await response.blob();
      const downloadUrl = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = downloadUrl;
      a.download = `expenses-${startDate}-${endDate}.csv`;
      a.click();
      URL.revokeObjectURL(downloadUrl);
    } else {
      const response = await fetch(url);
      const data = await response.json();
      const blob = new Blob([JSON.stringify(data, null, 2)], { type: 'application/json' });
      const downloadUrl = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = downloadUrl;
      a.download = `expenses-${startDate}-${endDate}.json`;
      a.click();
      URL.revokeObjectURL(downloadUrl);
    }
  };

  const filteredExpenses = expenses?.filter(expense => {
    const matchesSearch = expense.title.toLowerCase().includes(searchTerm.toLowerCase()) ||
                         expense.description.toLowerCase().includes(searchTerm.toLowerCase());
    const matchesStatus = statusFilter === 'all' || expense.status === statusFilter;
    const matchesCategory = categoryFilter === 'all' || expense.category === categoryFilter;
    
    return matchesSearch && matchesStatus && matchesCategory;
  }) || [];

  const formatCurrency = (amount: number) => {
    return new Intl.NumberFormat('en-US', {
      style: 'currency',
      currency: 'USD',
    }).format(amount);
  };

  const formatDate = (dateString: string) => {
    return new Date(dateString).toLocaleDateString('en-US', {
      year: 'numeric',
      month: 'short',
      day: 'numeric',
    });
  };

  const getStatusColor = (status: string) => {
    switch (status) {
      case 'approved':
        return 'bg-green-100 text-green-800 dark:bg-green-900 dark:text-green-200';
      case 'rejected':
        return 'bg-red-100 text-red-800 dark:bg-red-900 dark:text-red-200';
      case 'pending':
        return 'bg-yellow-100 text-yellow-800 dark:bg-yellow-900 dark:text-yellow-200';
      default:
        return 'bg-gray-100 text-gray-800 dark:bg-gray-900 dark:text-gray-200';
    }
  };

  if (isLoading) {
    return (
      <div className="p-6">
        <div className="animate-pulse">
          <div className="h-8 bg-gray-200 dark:bg-gray-700 rounded mb-6"></div>
          <div className="space-y-4">
            {[...Array(5)].map((_, i) => (
              <div key={i} className="h-20 bg-gray-200 dark:bg-gray-700 rounded-lg"></div>
            ))}
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="p-6">
      <div className="flex items-center justify-between mb-6">
        <h1 className="text-3xl font-bold text-gray-900 dark:text-gray-100">
          Expense Reports
        </h1>
        <div className="flex items-center gap-3">
          <Button
            variant="outline"
            onClick={() => handleExport('csv')}
            className="flex items-center gap-2"
          >
            <Download size={16} />
            Export CSV
          </Button>
          <Button
            variant="outline"
            onClick={() => handleExport('json')}
            className="flex items-center gap-2"
          >
            <Download size={16} />
            Export JSON
          </Button>
          <Link href="/expenses/new">
            <Button className="flex items-center gap-2">
              <Plus size={16} />
              New Expense
            </Button>
          </Link>
        </div>
      </div>

      {/* Filters */}
      <Card className="mb-6">
        <CardContent className="p-4">
          <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
            <div className="relative">
              <Search className="absolute left-3 top-3 h-4 w-4 text-gray-400" />
              <Input
                placeholder="Search expenses..."
                value={searchTerm}
                onChange={(e) => setSearchTerm(e.target.value)}
                className="pl-10"
              />
            </div>
            <Select value={statusFilter} onChange={(e) => setStatusFilter(e.target.value)}>
              <SelectItem value="all">All Statuses</SelectItem>
              <SelectItem value="pending">Pending</SelectItem>
              <SelectItem value="approved">Approved</SelectItem>
              <SelectItem value="rejected">Rejected</SelectItem>
            </Select>
            <Select value={categoryFilter} onChange={(e) => setCategoryFilter(e.target.value)}>
              <SelectItem value="all">All Categories</SelectItem>
              <SelectItem value="travel">Travel</SelectItem>
              <SelectItem value="meals">Meals</SelectItem>
              <SelectItem value="office">Office</SelectItem>
              <SelectItem value="software">Software</SelectItem>
              <SelectItem value="training">Training</SelectItem>
              <SelectItem value="other">Other</SelectItem>
            </Select>
            <div className="flex items-center text-sm text-gray-600 dark:text-gray-400">
              <Filter className="h-4 w-4 mr-2" />
              {filteredExpenses.length} of {expenses?.length || 0} expenses
            </div>
          </div>
        </CardContent>
      </Card>

      {/* Expenses List */}
      <Card>
        <CardHeader>
          <CardTitle>Expenses ({filteredExpenses.length})</CardTitle>
        </CardHeader>
        <CardContent>
          {filteredExpenses.length > 0 ? (
            <div className="space-y-4">
              {filteredExpenses.map((expense) => {
                const user = users?.find(u => u.id === expense.userId);
                return (
                  <div key={expense.id} className="flex items-center justify-between p-4 bg-gray-50 dark:bg-gray-700 rounded-lg">
                    <div className="flex-1">
                      <div className="flex items-center gap-4">
                        <div className="flex-1">
                          <h4 className="font-medium text-gray-900 dark:text-gray-100">
                            {expense.title}
                          </h4>
                          <p className="text-sm text-gray-600 dark:text-gray-400">
                            {user?.name || 'Unknown User'} • {expense.category} • {formatDate(expense.submittedAt)}
                          </p>
                          <p className="text-sm text-gray-500 dark:text-gray-400 mt-1">
                            {expense.description}
                          </p>
                        </div>
                        <div className="text-right">
                          <p className="font-medium text-gray-900 dark:text-gray-100">
                            {formatCurrency(expense.amount)}
                          </p>
                          <span className={`inline-block px-2 py-1 text-xs rounded-full capitalize ${getStatusColor(expense.status)}`}>
                            {expense.status}
                          </span>
                        </div>
                      </div>
                    </div>
                    <Link href={`/expenses/${expense.id}`}>
                      <Button variant="outline" size="sm">
                        View Details
                      </Button>
                    </Link>
                  </div>
                );
              })}
            </div>
          ) : (
            <div className="text-center py-8">
              <p className="text-gray-500 dark:text-gray-400">No expenses found</p>
              <Link href="/expenses/new">
                <Button className="mt-4">
                  Create Your First Expense
                </Button>
              </Link>
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  );
};

export default ExpensesList;