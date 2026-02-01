/**
 * @file budget_template_dialog.tsx
 * @brief Budget Template Dialogs for Rent, Mortgage, and Salary budgets
 * @author sailing-innocent
 * @date 2026-02-01
 */

import React, { useState } from 'react'
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from '@/components/ui/dialog'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Badge } from '@/components/ui/badge'
import {
  api_create_rent_budget,
  api_create_mortgage_budget,
  api_create_salary_budget,
} from '@lib/api/money'
import { Money } from '@lib/utils/money'

interface BudgetTemplateDialogProps {
  onSuccess?: () => void
}

const BudgetTemplateDialog: React.FC<BudgetTemplateDialogProps> = ({ onSuccess }) => {
  const [open, setOpen] = useState(false)
  const [isSubmitting, setIsSubmitting] = useState(false)
  const [activeTab, setActiveTab] = useState('rent')

  // Rent form state
  const [rentName, setRentName] = useState('')
  const [monthlyRent, setMonthlyRent] = useState('')
  const [deposit, setDeposit] = useState('')
  const [rentStartDate, setRentStartDate] = useState('')
  const [rentEndDate, setRentEndDate] = useState('')
  const [rentDescription, setRentDescription] = useState('')

  // Mortgage form state
  const [mortgageName, setMortgageName] = useState('')
  const [downPayment, setDownPayment] = useState('')
  const [monthlyPayment, setMonthlyPayment] = useState('')
  const [monthlyInterest, setMonthlyInterest] = useState('')
  const [loanMonths, setLoanMonths] = useState('360')
  const [mortgageStartDate, setMortgageStartDate] = useState('')
  const [mortgageDescription, setMortgageDescription] = useState('')

  // Salary form state
  const [salaryName, setSalaryName] = useState('')
  const [monthlySalary, setMonthlySalary] = useState('')
  const [salaryYear, setSalaryYear] = useState(new Date().getFullYear().toString())
  const [annualBonus, setAnnualBonus] = useState('')
  const [salaryDescription, setSalaryDescription] = useState('')

  const resetForms = () => {
    setRentName('')
    setMonthlyRent('')
    setDeposit('')
    setRentStartDate('')
    setRentEndDate('')
    setRentDescription('')
    setMortgageName('')
    setDownPayment('')
    setMonthlyPayment('')
    setMonthlyInterest('')
    setLoanMonths('360')
    setMortgageStartDate('')
    setMortgageDescription('')
    setSalaryName('')
    setMonthlySalary('')
    setSalaryYear(new Date().getFullYear().toString())
    setAnnualBonus('')
    setSalaryDescription('')
  }

  const handleCreateRent = async () => {
    if (!rentName || !monthlyRent || !deposit || !rentStartDate || !rentEndDate) {
      alert('请填写完整的租房信息')
      return
    }
    setIsSubmitting(true)
    try {
      await api_create_rent_budget({
        name: rentName,
        monthly_rent: monthlyRent,
        deposit: deposit,
        start_date: new Date(rentStartDate).getTime() / 1000,
        end_date: new Date(rentEndDate).getTime() / 1000,
        description: rentDescription,
      })
      resetForms()
      setOpen(false)
      onSuccess?.()
    } catch (error) {
      console.error('Failed to create rent budget:', error)
      alert('创建失败，请重试')
    } finally {
      setIsSubmitting(false)
    }
  }

  const handleCreateMortgage = async () => {
    if (!mortgageName || !downPayment || !monthlyPayment || !mortgageStartDate) {
      alert('请填写完整的房贷信息')
      return
    }
    setIsSubmitting(true)
    try {
      await api_create_mortgage_budget({
        name: mortgageName,
        down_payment: downPayment,
        monthly_payment: monthlyPayment,
        monthly_interest: monthlyInterest || '0',
        loan_months: parseInt(loanMonths) || 360,
        start_date: new Date(mortgageStartDate).getTime() / 1000,
        description: mortgageDescription,
      })
      resetForms()
      setOpen(false)
      onSuccess?.()
    } catch (error) {
      console.error('Failed to create mortgage budget:', error)
      alert('创建失败，请重试')
    } finally {
      setIsSubmitting(false)
    }
  }

  const handleCreateSalary = async () => {
    if (!salaryName || !monthlySalary || !salaryYear) {
      alert('请填写完整的工资信息')
      return
    }
    setIsSubmitting(true)
    try {
      await api_create_salary_budget({
        name: salaryName,
        monthly_salary: monthlySalary,
        year: parseInt(salaryYear),
        annual_bonus: annualBonus || '0',
        description: salaryDescription,
      })
      resetForms()
      setOpen(false)
      onSuccess?.()
    } catch (error) {
      console.error('Failed to create salary budget:', error)
      alert('创建失败，请重试')
    } finally {
      setIsSubmitting(false)
    }
  }

  // Calculate preview amounts
  const calculateRentTotal = () => {
    if (!monthlyRent || !deposit || !rentStartDate || !rentEndDate) return null
    try {
      const start = new Date(rentStartDate)
      const end = new Date(rentEndDate)
      const months = (end.getFullYear() - start.getFullYear()) * 12 + (end.getMonth() - start.getMonth()) + 1
      const totalRent = new Money(monthlyRent).value * months
      const totalDeposit = new Money(deposit).value
      return {
        months,
        totalRent: new Money(totalRent.toString()),
        totalDeposit: new Money(deposit),
        total: new Money((totalRent + totalDeposit).toString()),
      }
    } catch {
      return null
    }
  }

  const calculateMortgageTotal = () => {
    if (!downPayment || !monthlyPayment || !loanMonths) return null
    try {
      const months = parseInt(loanMonths) || 0
      const totalPayment = new Money(monthlyPayment).value * months
      const totalInterest = monthlyInterest ? new Money(monthlyInterest).value * months : 0
      const down = new Money(downPayment).value
      return {
        months,
        years: Math.floor(months / 12),
        totalPayment: new Money(totalPayment.toString()),
        totalInterest: new Money(totalInterest.toString()),
        total: new Money((down + totalPayment).toString()),
      }
    } catch {
      return null
    }
  }

  const calculateSalaryTotal = () => {
    if (!monthlySalary) return null
    try {
      const totalSalary = new Money(monthlySalary).value * 12
      const bonus = annualBonus ? new Money(annualBonus).value : 0
      return {
        totalSalary: new Money(totalSalary.toString()),
        bonus: new Money(bonus.toString()),
        total: new Money((totalSalary + bonus).toString()),
      }
    } catch {
      return null
    }
  }

  const rentPreview = calculateRentTotal()
  const mortgagePreview = calculateMortgageTotal()
  const salaryPreview = calculateSalaryTotal()

  return (
    <Dialog open={open} onOpenChange={setOpen}>
      <DialogTrigger asChild>
        <Button variant="outline">预算模板</Button>
      </DialogTrigger>
      <DialogContent className="max-w-2xl max-h-[90vh] overflow-y-auto">
        <DialogHeader>
          <DialogTitle>创建预算模板</DialogTitle>
          <DialogDescription>
            选择预算类型，快速创建常用预算
          </DialogDescription>
        </DialogHeader>

        <Tabs value={activeTab} onValueChange={setActiveTab}>
          <TabsList className="grid w-full grid-cols-3">
            <TabsTrigger value="rent">租房预算</TabsTrigger>
            <TabsTrigger value="mortgage">房贷预算</TabsTrigger>
            <TabsTrigger value="salary">工资预算</TabsTrigger>
          </TabsList>

          {/* 租房预算 */}
          <TabsContent value="rent" className="space-y-4">
            <Card>
              <CardHeader className="pb-3">
                <CardTitle className="text-base">租房合同预算</CardTitle>
                <CardDescription>追踪月租金和押金</CardDescription>
              </CardHeader>
              <CardContent className="space-y-4">
                <div className="grid gap-2">
                  <Label>预算名称</Label>
                  <Input
                    value={rentName}
                    onChange={(e) => setRentName(e.target.value)}
                    placeholder="如：2026年上海租房"
                  />
                </div>
                <div className="grid grid-cols-2 gap-4">
                  <div className="grid gap-2">
                    <Label>月租金</Label>
                    <Input
                      type="number"
                      value={monthlyRent}
                      onChange={(e) => setMonthlyRent(e.target.value)}
                      placeholder="3500"
                    />
                  </div>
                  <div className="grid gap-2">
                    <Label>押金</Label>
                    <Input
                      type="number"
                      value={deposit}
                      onChange={(e) => setDeposit(e.target.value)}
                      placeholder="7000"
                    />
                  </div>
                </div>
                <div className="grid grid-cols-2 gap-4">
                  <div className="grid gap-2">
                    <Label>合同开始日期</Label>
                    <Input
                      type="date"
                      value={rentStartDate}
                      onChange={(e) => setRentStartDate(e.target.value)}
                    />
                  </div>
                  <div className="grid gap-2">
                    <Label>合同结束日期</Label>
                    <Input
                      type="date"
                      value={rentEndDate}
                      onChange={(e) => setRentEndDate(e.target.value)}
                    />
                  </div>
                </div>
                <div className="grid gap-2">
                  <Label>描述（可选）</Label>
                  <Input
                    value={rentDescription}
                    onChange={(e) => setRentDescription(e.target.value)}
                    placeholder="合同备注..."
                  />
                </div>

                {rentPreview && (
                  <div className="p-3 bg-muted rounded-md space-y-2">
                    <div className="text-sm font-medium">预算预览</div>
                    <div className="grid grid-cols-2 gap-2 text-sm">
                      <div>租期：{rentPreview.months} 个月</div>
                      <div>总租金：{rentPreview.totalRent.format()}</div>
                      <div>押金：{rentPreview.totalDeposit.format()} <Badge variant="outline" className="ml-1">可退还</Badge></div>
                      <div className="font-semibold">总预算：{rentPreview.total.format()}</div>
                    </div>
                  </div>
                )}
              </CardContent>
            </Card>
            <DialogFooter>
              <Button variant="outline" onClick={() => setOpen(false)}>取消</Button>
              <Button onClick={handleCreateRent} disabled={isSubmitting}>
                {isSubmitting ? '创建中...' : '创建租房预算'}
              </Button>
            </DialogFooter>
          </TabsContent>

          {/* 房贷预算 */}
          <TabsContent value="mortgage" className="space-y-4">
            <Card>
              <CardHeader className="pb-3">
                <CardTitle className="text-base">房贷预算</CardTitle>
                <CardDescription>追踪首付和月供</CardDescription>
              </CardHeader>
              <CardContent className="space-y-4">
                <div className="grid gap-2">
                  <Label>预算名称</Label>
                  <Input
                    value={mortgageName}
                    onChange={(e) => setMortgageName(e.target.value)}
                    placeholder="如：购房贷款2026"
                  />
                </div>
                <div className="grid grid-cols-2 gap-4">
                  <div className="grid gap-2">
                    <Label>首付款</Label>
                    <Input
                      type="number"
                      value={downPayment}
                      onChange={(e) => setDownPayment(e.target.value)}
                      placeholder="500000"
                    />
                  </div>
                  <div className="grid gap-2">
                    <Label>月供</Label>
                    <Input
                      type="number"
                      value={monthlyPayment}
                      onChange={(e) => setMonthlyPayment(e.target.value)}
                      placeholder="8000"
                    />
                  </div>
                </div>
                <div className="grid grid-cols-2 gap-4">
                  <div className="grid gap-2">
                    <Label>月均利息（可选）</Label>
                    <Input
                      type="number"
                      value={monthlyInterest}
                      onChange={(e) => setMonthlyInterest(e.target.value)}
                      placeholder="3000"
                    />
                  </div>
                  <div className="grid gap-2">
                    <Label>贷款期数（月）</Label>
                    <Input
                      type="number"
                      value={loanMonths}
                      onChange={(e) => setLoanMonths(e.target.value)}
                      placeholder="360"
                    />
                  </div>
                </div>
                <div className="grid gap-2">
                  <Label>贷款开始日期</Label>
                  <Input
                    type="date"
                    value={mortgageStartDate}
                    onChange={(e) => setMortgageStartDate(e.target.value)}
                  />
                </div>
                <div className="grid gap-2">
                  <Label>描述（可选）</Label>
                  <Input
                    value={mortgageDescription}
                    onChange={(e) => setMortgageDescription(e.target.value)}
                    placeholder="贷款备注..."
                  />
                </div>

                {mortgagePreview && (
                  <div className="p-3 bg-muted rounded-md space-y-2">
                    <div className="text-sm font-medium">预算预览</div>
                    <div className="grid grid-cols-2 gap-2 text-sm">
                      <div>贷款期限：{mortgagePreview.years}年（{mortgagePreview.months}期）</div>
                      <div>首付款：{new Money(downPayment).format()}</div>
                      <div>总月供：{mortgagePreview.totalPayment.format()}</div>
                      <div>总利息：{mortgagePreview.totalInterest.format()}</div>
                      <div className="font-semibold col-span-2">总支出：{mortgagePreview.total.format()}</div>
                    </div>
                  </div>
                )}
              </CardContent>
            </Card>
            <DialogFooter>
              <Button variant="outline" onClick={() => setOpen(false)}>取消</Button>
              <Button onClick={handleCreateMortgage} disabled={isSubmitting}>
                {isSubmitting ? '创建中...' : '创建房贷预算'}
              </Button>
            </DialogFooter>
          </TabsContent>

          {/* 工资预算 */}
          <TabsContent value="salary" className="space-y-4">
            <Card>
              <CardHeader className="pb-3">
                <CardTitle className="text-base">年度工资预算（收入）</CardTitle>
                <CardDescription>追踪月薪和年终奖</CardDescription>
              </CardHeader>
              <CardContent className="space-y-4">
                <div className="grid gap-2">
                  <Label>预算名称</Label>
                  <Input
                    value={salaryName}
                    onChange={(e) => setSalaryName(e.target.value)}
                    placeholder="如：2026年工资收入"
                  />
                </div>
                <div className="grid grid-cols-2 gap-4">
                  <div className="grid gap-2">
                    <Label>月薪（税后）</Label>
                    <Input
                      type="number"
                      value={monthlySalary}
                      onChange={(e) => setMonthlySalary(e.target.value)}
                      placeholder="20000"
                    />
                  </div>
                  <div className="grid gap-2">
                    <Label>年份</Label>
                    <Input
                      type="number"
                      value={salaryYear}
                      onChange={(e) => setSalaryYear(e.target.value)}
                      placeholder="2026"
                    />
                  </div>
                </div>
                <div className="grid gap-2">
                  <Label>年终奖（可选）</Label>
                  <Input
                    type="number"
                    value={annualBonus}
                    onChange={(e) => setAnnualBonus(e.target.value)}
                    placeholder="50000"
                  />
                </div>
                <div className="grid gap-2">
                  <Label>描述（可选）</Label>
                  <Input
                    value={salaryDescription}
                    onChange={(e) => setSalaryDescription(e.target.value)}
                    placeholder="工资备注..."
                  />
                </div>

                {salaryPreview && (
                  <div className="p-3 bg-muted rounded-md space-y-2">
                    <div className="text-sm font-medium">预算预览</div>
                    <div className="grid grid-cols-2 gap-2 text-sm">
                      <div>年薪（12月）：{salaryPreview.totalSalary.format()}</div>
                      <div>年终奖：{salaryPreview.bonus.format()}</div>
                      <div className="font-semibold col-span-2">年度预计收入：{salaryPreview.total.format()}</div>
                    </div>
                    <Badge variant="secondary">收入预算</Badge>
                  </div>
                )}
              </CardContent>
            </Card>
            <DialogFooter>
              <Button variant="outline" onClick={() => setOpen(false)}>取消</Button>
              <Button onClick={handleCreateSalary} disabled={isSubmitting}>
                {isSubmitting ? '创建中...' : '创建工资预算'}
              </Button>
            </DialogFooter>
          </TabsContent>
        </Tabs>
      </DialogContent>
    </Dialog>
  )
}

export default BudgetTemplateDialog
