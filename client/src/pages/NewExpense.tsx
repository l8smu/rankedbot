import React from 'react';
import { useForm } from 'react-hook-form';
import { zodResolver } from '@hookform/resolvers/zod';
import { useMutation, useQueryClient } from '@tanstack/react-query';
import { useLocation } from 'wouter';
import { z } from 'zod';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Input, Textarea, Select, SelectItem } from '@/components/ui/input';
import { Form, FormField, FormItem, FormLabel, FormMessage } from '@/components/ui/form';
import { useToast } from '@/hooks/use-toast';
import { insertExpenseSchema } from '../../../shared/schema';
import { apiRequest } from '@/lib/queryClient';

const formSchema = insertExpenseSchema.extend({
  amount: z.coerce.number().min(0.01, 'Amount must be greater than 0'),
});

type FormData = z.infer<typeof formSchema>;

const NewExpense: React.FC = () => {
  const [, navigate] = useLocation();
  const { toast } = useToast();
  const queryClient = useQueryClient();
  
  const form = useForm<FormData>({
    resolver: zodResolver(formSchema),
    defaultValues: {
      userId: 'user-3', // Default to employee user for demo
      title: '',
      description: '',
      amount: 0,
      category: 'other',
      status: 'pending',
      rejectionReason: '',
    },
  });

  const mutation = useMutation({
    mutationFn: (data: FormData) => apiRequest('/api/expenses', {
      method: 'POST',
      body: JSON.stringify(data),
    }),
    onSuccess: () => {
      toast({
        title: 'Success',
        description: 'Expense submitted successfully',
        variant: 'success',
      });
      queryClient.invalidateQueries({ queryKey: ['/api/expenses'] });
      queryClient.invalidateQueries({ queryKey: ['/api/dashboard/stats'] });
      navigate('/expenses');
    },
    onError: (error) => {
      toast({
        title: 'Error',
        description: 'Failed to submit expense. Please try again.',
        variant: 'error',
      });
    },
  });

  const onSubmit = (data: FormData) => {
    mutation.mutate(data);
  };

  return (
    <div className="p-6">
      <div className="max-w-2xl mx-auto">
        <h1 className="text-3xl font-bold text-gray-900 dark:text-gray-100 mb-6">
          New Expense Report
        </h1>

        <Card>
          <CardHeader>
            <CardTitle>Expense Details</CardTitle>
          </CardHeader>
          <CardContent>
            <Form form={form} onSubmit={onSubmit} className="space-y-6">
              <FormField
                control={form.control}
                name="title"
                render={({ field }) => (
                  <FormItem>
                    <FormLabel>Title</FormLabel>
                    <Input
                      {...field}
                      placeholder="Enter expense title"
                      className="w-full"
                    />
                    <FormMessage>{form.formState.errors.title?.message}</FormMessage>
                  </FormItem>
                )}
              />

              <FormField
                control={form.control}
                name="description"
                render={({ field }) => (
                  <FormItem>
                    <FormLabel>Description</FormLabel>
                    <Textarea
                      {...field}
                      placeholder="Describe the expense..."
                      rows={4}
                      className="w-full"
                    />
                    <FormMessage>{form.formState.errors.description?.message}</FormMessage>
                  </FormItem>
                )}
              />

              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                <FormField
                  control={form.control}
                  name="amount"
                  render={({ field }) => (
                    <FormItem>
                      <FormLabel>Amount ($)</FormLabel>
                      <Input
                        {...field}
                        type="number"
                        step="0.01"
                        placeholder="0.00"
                        className="w-full"
                      />
                      <FormMessage>{form.formState.errors.amount?.message}</FormMessage>
                    </FormItem>
                  )}
                />

                <FormField
                  control={form.control}
                  name="category"
                  render={({ field }) => (
                    <FormItem>
                      <FormLabel>Category</FormLabel>
                      <Select {...field}>
                        <SelectItem value="travel">Travel</SelectItem>
                        <SelectItem value="meals">Meals</SelectItem>
                        <SelectItem value="office">Office Supplies</SelectItem>
                        <SelectItem value="software">Software</SelectItem>
                        <SelectItem value="training">Training</SelectItem>
                        <SelectItem value="other">Other</SelectItem>
                      </Select>
                      <FormMessage>{form.formState.errors.category?.message}</FormMessage>
                    </FormItem>
                  )}
                />
              </div>

              <div className="flex items-center gap-4 pt-4">
                <Button
                  type="submit"
                  disabled={mutation.isPending}
                  className="flex-1"
                >
                  {mutation.isPending ? 'Submitting...' : 'Submit Expense'}
                </Button>
                <Button
                  type="button"
                  variant="outline"
                  onClick={() => navigate('/expenses')}
                  className="flex-1"
                >
                  Cancel
                </Button>
              </div>
            </Form>
          </CardContent>
        </Card>

        <div className="mt-6 p-4 bg-blue-50 dark:bg-blue-900/20 rounded-lg">
          <h3 className="font-medium text-blue-900 dark:text-blue-100 mb-2">
            Expense Policy Reminder
          </h3>
          <ul className="text-sm text-blue-800 dark:text-blue-200 space-y-1">
            <li>• All expenses must be submitted within 30 days</li>
            <li>• Receipts should be attached for amounts over $25</li>
            <li>• Business meals require attendee information</li>
            <li>• Travel expenses need pre-approval for amounts over $500</li>
          </ul>
        </div>
      </div>
    </div>
  );
};

export default NewExpense;