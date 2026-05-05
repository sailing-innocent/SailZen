import { useState } from 'react'
import { Button } from '@components/ui/button'
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
  DialogFooter,
  DialogClose,
} from '@components/ui/dialog'
import { Input } from '@components/ui/input'
import type { AccountData } from '@lib/data'
import { Select, SelectContent, SelectGroup, SelectItem, SelectLabel, SelectTrigger, SelectValue } from '@components/ui/select'
import { useIsMobile } from '@/hooks/use-mobile'

interface FixAccountDialogProps {
  accounts: AccountData[]
  handleFixAccount: (id: number, newBalance: string) => void
}

const AccountFixDialog = (props: FixAccountDialogProps) => {
  const [fixedBalance, setFixedBalance] = useState<string>('0.0')
  const [accountId, setAccountId] = useState<number>(-1)
  const { handleFixAccount } = props
  const isMobile = useIsMobile()
  return (
    <Dialog>
      <DialogTrigger asChild>
        <Button variant="outline">Fix Account</Button>
      </DialogTrigger>
      <DialogContent className={isMobile ? 'max-w-[95vw] max-h-[85vh] overflow-y-auto' : ''}>
        <DialogHeader>
          <DialogTitle>Fix Account</DialogTitle>
          <DialogDescription>Fix the account</DialogDescription>
        </DialogHeader>
        <Select onValueChange={(value) => setAccountId(parseInt(value))} value={accountId.toString()}>
          <SelectTrigger className="w-full">
            <SelectValue placeholder="Select Account" />
          </SelectTrigger>
          <SelectContent>
            <SelectGroup>
              <SelectLabel>Accounts</SelectLabel>
              {props.accounts.map((account) => (
                <SelectItem key={account.id} value={account.id.toString()}>
                  {account.name}
                </SelectItem>
              ))}
            </SelectGroup>
          </SelectContent>
        </Select>
        <Input placeholder="new balance to fix" value={fixedBalance} onChange={(e) => setFixedBalance(e.target.value)} />
        <DialogFooter className="sm:justify-start">
          <DialogClose asChild>
            <Button
              type="button"
              onClick={() => {
                if (accountId !== -1) {
                  handleFixAccount(accountId, fixedBalance)
                }
              }}
              variant="secondary"
            >
              Submit
            </Button>
          </DialogClose>
          <DialogClose asChild>
            <Button type="button" variant="secondary">
              Cancel
            </Button>
          </DialogClose>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}

export default AccountFixDialog
