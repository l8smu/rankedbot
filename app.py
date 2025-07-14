#!/usr/bin/env python3
"""
Professional Expense Reporting and Approval Automation Tool
A comprehensive business expense management system with automated approval workflows
"""

import json
import os
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any
import csv
import io

# Simple in-memory storage for demo purposes
# In production, this would be a proper database
class ExpenseStorage:
    def __init__(self):
        self.users = {
            'user-1': {
                'id': 'user-1',
                'name': 'John Smith',
                'email': 'john.smith@company.com',
                'role': 'admin',
                'department': 'Finance',
            },
            'user-2': {
                'id': 'user-2',
                'name': 'Sarah Johnson',
                'email': 'sarah.johnson@company.com',
                'role': 'manager',
                'department': 'Engineering',
                'managerId': 'user-1',
            },
            'user-3': {
                'id': 'user-3',
                'name': 'Mike Davis',
                'email': 'mike.davis@company.com',
                'role': 'employee',
                'department': 'Engineering',
                'managerId': 'user-2',
            }
        }
        
        self.expenses = {
            'exp-1': {
                'id': 'exp-1',
                'userId': 'user-3',
                'title': 'Business Trip to NYC',
                'description': 'Flight and hotel for client meeting',
                'amount': 1250.00,
                'category': 'travel',
                'status': 'pending',
                'submittedAt': datetime.now().isoformat(),
            },
            'exp-2': {
                'id': 'exp-2',
                'userId': 'user-3',
                'title': 'Team Lunch',
                'description': 'Lunch with development team',
                'amount': 85.50,
                'category': 'meals',
                'status': 'approved',
                'submittedAt': (datetime.now() - timedelta(days=1)).isoformat(),
                'approvedAt': datetime.now().isoformat(),
                'approvedBy': 'user-2',
            },
            'exp-3': {
                'id': 'exp-3',
                'userId': 'user-2',
                'title': 'Office Supplies',
                'description': 'Whiteboard markers and sticky notes',
                'amount': 45.30,
                'category': 'office',
                'status': 'approved',
                'submittedAt': (datetime.now() - timedelta(days=2)).isoformat(),
                'approvedAt': (datetime.now() - timedelta(days=1)).isoformat(),
                'approvedBy': 'user-1',
            },
        }
        
        self.approvals = {}
        self.expense_counter = 4
        
    def get_dashboard_stats(self, user_id: Optional[str] = None) -> Dict:
        """Get dashboard statistics"""
        expenses = list(self.expenses.values())
        if user_id:
            expenses = [e for e in expenses if e['userId'] == user_id]
        
        current_month = datetime.now().month
        current_year = datetime.now().year
        
        monthly_expenses = [
            e for e in expenses 
            if datetime.fromisoformat(e['submittedAt']).month == current_month and
               datetime.fromisoformat(e['submittedAt']).year == current_year
        ]
        
        return {
            'totalExpenses': len(expenses),
            'pendingApprovals': len([e for e in expenses if e['status'] == 'pending']),
            'approvedAmount': sum(e['amount'] for e in expenses if e['status'] == 'approved'),
            'rejectedCount': len([e for e in expenses if e['status'] == 'rejected']),
            'monthlyTotal': sum(e['amount'] for e in monthly_expenses),
        }
    
    def create_expense(self, expense_data: Dict) -> Dict:
        """Create a new expense"""
        expense_id = f'exp-{self.expense_counter}'
        self.expense_counter += 1
        
        expense = {
            'id': expense_id,
            'submittedAt': datetime.now().isoformat(),
            **expense_data
        }
        
        self.expenses[expense_id] = expense
        return expense
    
    def approve_expense(self, expense_id: str, approver_id: str) -> Dict:
        """Approve an expense"""
        if expense_id not in self.expenses:
            raise ValueError('Expense not found')
        
        expense = self.expenses[expense_id]
        expense.update({
            'status': 'approved',
            'approvedAt': datetime.now().isoformat(),
            'approvedBy': approver_id
        })
        
        # Create approval record
        approval = {
            'id': f'approval-{len(self.approvals) + 1}',
            'expenseId': expense_id,
            'approverId': approver_id,
            'action': 'approve',
            'timestamp': datetime.now().isoformat()
        }
        self.approvals[approval['id']] = approval
        
        return {'expense': expense, 'approval': approval}
    
    def reject_expense(self, expense_id: str, approver_id: str, reason: str) -> Dict:
        """Reject an expense"""
        if expense_id not in self.expenses:
            raise ValueError('Expense not found')
        
        expense = self.expenses[expense_id]
        expense.update({
            'status': 'rejected',
            'rejectedAt': datetime.now().isoformat(),
            'rejectedBy': approver_id,
            'rejectionReason': reason
        })
        
        # Create approval record
        approval = {
            'id': f'approval-{len(self.approvals) + 1}',
            'expenseId': expense_id,
            'approverId': approver_id,
            'action': 'reject',
            'reason': reason,
            'timestamp': datetime.now().isoformat()
        }
        self.approvals[approval['id']] = approval
        
        return {'expense': expense, 'approval': approval}
    
    def export_expenses(self, start_date: str, end_date: str, format_type: str = 'json') -> Any:
        """Export expenses in specified format"""
        start_dt = datetime.fromisoformat(start_date)
        end_dt = datetime.fromisoformat(end_date)
        
        filtered_expenses = [
            e for e in self.expenses.values()
            if start_dt <= datetime.fromisoformat(e['submittedAt']) <= end_dt
        ]
        
        if format_type == 'csv':
            output = io.StringIO()
            writer = csv.writer(output)
            
            # Write header
            writer.writerow(['ID', 'User', 'Title', 'Description', 'Amount', 'Category', 'Status', 'Submitted Date', 'Approved Date', 'Approved By'])
            
            # Write data
            for expense in filtered_expenses:
                user = self.users.get(expense['userId'], {})
                approver = self.users.get(expense.get('approvedBy', ''), {})
                
                writer.writerow([
                    expense['id'],
                    user.get('name', 'Unknown'),
                    expense['title'],
                    expense['description'].replace(',', ';'),
                    expense['amount'],
                    expense['category'],
                    expense['status'],
                    expense['submittedAt'],
                    expense.get('approvedAt', ''),
                    approver.get('name', '')
                ])
            
            return output.getvalue()
        
        else:
            return {
                'expenses': filtered_expenses,
                'users': list(self.users.values()),
                'totalAmount': sum(e['amount'] for e in filtered_expenses),
                'dateRange': {
                    'start': start_date,
                    'end': end_date
                }
            }

# Initialize storage
storage = ExpenseStorage()

def display_dashboard():
    """Display dashboard information"""
    stats = storage.get_dashboard_stats()
    
    print("=" * 60)
    print("           EXPENSE TRACKER DASHBOARD")
    print("=" * 60)
    print(f"Total Expenses: {stats['totalExpenses']}")
    print(f"Pending Approvals: {stats['pendingApprovals']}")
    print(f"Approved Amount: ${stats['approvedAmount']:,.2f}")
    print(f"Rejected Count: {stats['rejectedCount']}")
    print(f"Monthly Total: ${stats['monthlyTotal']:,.2f}")
    print()
    
    print("Recent Expenses:")
    print("-" * 40)
    for expense in list(storage.expenses.values())[:5]:
        user = storage.users.get(expense['userId'], {})
        status_symbol = "✓" if expense['status'] == 'approved' else "⏳" if expense['status'] == 'pending' else "✗"
        print(f"{status_symbol} {expense['title'][:30]} - ${expense['amount']:,.2f}")
        print(f"   By: {user.get('name', 'Unknown')} | Status: {expense['status'].upper()}")
        print()

def display_menu():
    """Display main menu"""
    print("=" * 60)
    print("           EXPENSE MANAGEMENT SYSTEM")
    print("=" * 60)
    print("1. View Dashboard")
    print("2. View All Expenses")
    print("3. Create New Expense")
    print("4. Approve/Reject Expense")
    print("5. Export Expenses")
    print("6. Exit")
    print("-" * 60)

def create_new_expense():
    """Create a new expense interactively"""
    print("\n--- Create New Expense ---")
    
    title = input("Enter expense title: ").strip()
    description = input("Enter description: ").strip()
    
    while True:
        try:
            amount = float(input("Enter amount ($): ").strip())
            if amount <= 0:
                print("Amount must be greater than 0")
                continue
            break
        except ValueError:
            print("Please enter a valid number")
    
    print("\nCategories: travel, meals, office, software, training, other")
    category = input("Enter category: ").strip().lower()
    if category not in ['travel', 'meals', 'office', 'software', 'training', 'other']:
        category = 'other'
    
    expense_data = {
        'userId': 'user-3',  # Default to employee user
        'title': title,
        'description': description,
        'amount': amount,
        'category': category,
        'status': 'pending'
    }
    
    expense = storage.create_expense(expense_data)
    print(f"\n✓ Expense created successfully with ID: {expense['id']}")
    print(f"Title: {expense['title']}")
    print(f"Amount: ${expense['amount']:,.2f}")
    print(f"Status: {expense['status'].upper()}")

def view_expenses():
    """View all expenses"""
    print("\n--- All Expenses ---")
    
    if not storage.expenses:
        print("No expenses found.")
        return
    
    for expense in storage.expenses.values():
        user = storage.users.get(expense['userId'], {})
        status_symbol = "✓" if expense['status'] == 'approved' else "⏳" if expense['status'] == 'pending' else "✗"
        
        print(f"\n{status_symbol} ID: {expense['id']}")
        print(f"   Title: {expense['title']}")
        print(f"   User: {user.get('name', 'Unknown')}")
        print(f"   Amount: ${expense['amount']:,.2f}")
        print(f"   Category: {expense['category']}")
        print(f"   Status: {expense['status'].upper()}")
        print(f"   Submitted: {expense['submittedAt'][:10]}")
        
        if expense['status'] == 'approved':
            approver = storage.users.get(expense.get('approvedBy', ''), {})
            print(f"   Approved by: {approver.get('name', 'Unknown')}")
        elif expense['status'] == 'rejected':
            rejector = storage.users.get(expense.get('rejectedBy', ''), {})
            print(f"   Rejected by: {rejector.get('name', 'Unknown')}")
            if expense.get('rejectionReason'):
                print(f"   Reason: {expense['rejectionReason']}")

def approve_reject_expense():
    """Approve or reject an expense"""
    print("\n--- Expense Approval ---")
    
    pending_expenses = [e for e in storage.expenses.values() if e['status'] == 'pending']
    
    if not pending_expenses:
        print("No pending expenses found.")
        return
    
    print("Pending Expenses:")
    for i, expense in enumerate(pending_expenses, 1):
        user = storage.users.get(expense['userId'], {})
        print(f"{i}. {expense['title']} - ${expense['amount']:,.2f} by {user.get('name', 'Unknown')}")
    
    while True:
        try:
            choice = int(input(f"\nSelect expense (1-{len(pending_expenses)}): ").strip())
            if 1 <= choice <= len(pending_expenses):
                selected_expense = pending_expenses[choice - 1]
                break
            else:
                print("Invalid selection")
        except ValueError:
            print("Please enter a valid number")
    
    print(f"\nSelected: {selected_expense['title']}")
    print(f"Amount: ${selected_expense['amount']:,.2f}")
    print(f"Description: {selected_expense['description']}")
    
    action = input("\nEnter 'approve' or 'reject': ").strip().lower()
    
    if action == 'approve':
        result = storage.approve_expense(selected_expense['id'], 'user-2')  # Manager approval
        print(f"\n✓ Expense approved successfully!")
        print(f"Approved by: {storage.users['user-2']['name']}")
    
    elif action == 'reject':
        reason = input("Enter rejection reason: ").strip()
        result = storage.reject_expense(selected_expense['id'], 'user-2', reason)
        print(f"\n✗ Expense rejected.")
        print(f"Rejected by: {storage.users['user-2']['name']}")
        print(f"Reason: {reason}")
    
    else:
        print("Invalid action. Please enter 'approve' or 'reject'")

def export_expenses():
    """Export expenses to CSV or JSON"""
    print("\n--- Export Expenses ---")
    
    start_date = input("Enter start date (YYYY-MM-DD) or press Enter for last 30 days: ").strip()
    if not start_date:
        start_date = (datetime.now() - timedelta(days=30)).isoformat()
    else:
        start_date = datetime.fromisoformat(start_date).isoformat()
    
    end_date = input("Enter end date (YYYY-MM-DD) or press Enter for today: ").strip()
    if not end_date:
        end_date = datetime.now().isoformat()
    else:
        end_date = datetime.fromisoformat(end_date).isoformat()
    
    format_type = input("Export format (csv/json): ").strip().lower()
    if format_type not in ['csv', 'json']:
        format_type = 'json'
    
    try:
        export_data = storage.export_expenses(start_date, end_date, format_type)
        
        filename = f"expenses_export_{datetime.now().strftime('%Y%m%d_%H%M%S')}.{format_type}"
        
        with open(filename, 'w', newline='', encoding='utf-8') as f:
            if format_type == 'csv':
                f.write(export_data)
            else:
                json.dump(export_data, f, indent=2, default=str)
        
        print(f"\n✓ Expenses exported successfully to {filename}")
        
        if format_type == 'json':
            print(f"Total expenses: {len(export_data['expenses'])}")
            print(f"Total amount: ${export_data['totalAmount']:,.2f}")
        
    except Exception as e:
        print(f"Error exporting expenses: {e}")

def main():
    """Main application loop"""
    print("Welcome to the Professional Expense Reporting System!")
    print("A comprehensive tool for business expense management and approval automation.")
    
    while True:
        display_menu()
        
        try:
            choice = input("Enter your choice (1-6): ").strip()
            
            if choice == '1':
                display_dashboard()
            elif choice == '2':
                view_expenses()
            elif choice == '3':
                create_new_expense()
            elif choice == '4':
                approve_reject_expense()
            elif choice == '5':
                export_expenses()
            elif choice == '6':
                print("\nThank you for using the Expense Reporting System!")
                break
            else:
                print("Invalid choice. Please enter 1-6.")
            
            input("\nPress Enter to continue...")
            
        except KeyboardInterrupt:
            print("\n\nGoodbye!")
            break
        except Exception as e:
            print(f"An error occurred: {e}")
            input("Press Enter to continue...")

if __name__ == "__main__":
    main()