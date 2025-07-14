import { z } from 'zod';

// Expense status enum
export const ExpenseStatus = {
  PENDING: 'pending',
  APPROVED: 'approved',
  REJECTED: 'rejected',
  SUBMITTED: 'submitted'
} as const;

export type ExpenseStatusType = typeof ExpenseStatus[keyof typeof ExpenseStatus];

// Expense category enum
export const ExpenseCategory = {
  TRAVEL: 'travel',
  MEALS: 'meals',
  OFFICE: 'office',
  SOFTWARE: 'software',
  TRAINING: 'training',
  OTHER: 'other'
} as const;

export type ExpenseCategoryType = typeof ExpenseCategory[keyof typeof ExpenseCategory];

// User role enum
export const UserRole = {
  EMPLOYEE: 'employee',
  MANAGER: 'manager',
  ADMIN: 'admin'
} as const;

export type UserRoleType = typeof UserRole[keyof typeof UserRole];

// Base schemas
export const userSchema = z.object({
  id: z.string(),
  name: z.string(),
  email: z.string().email(),
  role: z.enum(['employee', 'manager', 'admin']),
  department: z.string(),
  managerId: z.string().optional(),
});

export const expenseSchema = z.object({
  id: z.string(),
  userId: z.string(),
  title: z.string(),
  description: z.string(),
  amount: z.number(),
  category: z.enum(['travel', 'meals', 'office', 'software', 'training', 'other']),
  status: z.enum(['pending', 'approved', 'rejected', 'submitted']),
  submittedAt: z.string(),
  approvedAt: z.string().optional(),
  approvedBy: z.string().optional(),
  rejectedAt: z.string().optional(),
  rejectedBy: z.string().optional(),
  rejectionReason: z.string().optional(),
  receiptUrl: z.string().optional(),
});

export const approvalSchema = z.object({
  id: z.string(),
  expenseId: z.string(),
  approverId: z.string(),
  action: z.enum(['approve', 'reject']),
  reason: z.string().optional(),
  timestamp: z.string(),
});

// Insert schemas
export const insertUserSchema = userSchema.omit({ id: true });
export const insertExpenseSchema = expenseSchema.omit({ 
  id: true, 
  submittedAt: true,
  approvedAt: true,
  approvedBy: true,
  rejectedAt: true,
  rejectedBy: true,
});
export const insertApprovalSchema = approvalSchema.omit({ id: true, timestamp: true });

// Types
export type User = z.infer<typeof userSchema>;
export type Expense = z.infer<typeof expenseSchema>;
export type Approval = z.infer<typeof approvalSchema>;
export type InsertUser = z.infer<typeof insertUserSchema>;
export type InsertExpense = z.infer<typeof insertExpenseSchema>;
export type InsertApproval = z.infer<typeof insertApprovalSchema>;

// Dashboard stats type
export type DashboardStats = {
  totalExpenses: number;
  pendingApprovals: number;
  approvedAmount: number;
  rejectedCount: number;
  monthlyTotal: number;
};

// Export summary type
export type ExpenseExport = {
  expenses: Expense[];
  users: User[];
  totalAmount: number;
  dateRange: {
    start: string;
    end: string;
  };
};