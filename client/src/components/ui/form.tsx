import React from 'react';
import { useForm as useReactHookForm, UseFormReturn, FieldValues, FieldPath } from 'react-hook-form';

interface FormProps<TFieldValues extends FieldValues> {
  children: React.ReactNode;
  onSubmit: (data: TFieldValues) => void;
  className?: string;
}

export const Form = <TFieldValues extends FieldValues>({
  children,
  onSubmit,
  className = '',
  ...props
}: FormProps<TFieldValues> & { form: UseFormReturn<TFieldValues> }) => {
  const { form } = props;
  
  return (
    <form onSubmit={form.handleSubmit(onSubmit)} className={className}>
      {children}
    </form>
  );
};

interface FormFieldProps<TFieldValues extends FieldValues> {
  control: UseFormReturn<TFieldValues>['control'];
  name: FieldPath<TFieldValues>;
  render: ({ field }: { field: any }) => React.ReactNode;
}

export const FormField = <TFieldValues extends FieldValues>({
  control,
  name,
  render,
}: FormFieldProps<TFieldValues>) => {
  return (
    <div>
      {render({ field: { name } })}
    </div>
  );
};

interface FormItemProps {
  children: React.ReactNode;
  className?: string;
}

export const FormItem: React.FC<FormItemProps> = ({ children, className = '' }) => {
  return <div className={`space-y-2 ${className}`}>{children}</div>;
};

export const FormLabel: React.FC<FormItemProps> = ({ children, className = '' }) => {
  return (
    <label className={`text-sm font-medium text-gray-700 dark:text-gray-300 ${className}`}>
      {children}
    </label>
  );
};

export const FormMessage: React.FC<FormItemProps> = ({ children, className = '' }) => {
  if (!children) return null;
  
  return (
    <p className={`text-sm text-red-600 dark:text-red-400 ${className}`}>
      {children}
    </p>
  );
};

export const useForm = useReactHookForm;