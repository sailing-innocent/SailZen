import React, { useState } from 'react'
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

export interface AddAccountDialogProps {
  handleCreateAccount: (name: string) => void
}

const AddAccountDialog = (props: AddAccountDialogProps) => {
  const { handleCreateAccount } = props
  const [name, setName] = useState<string>('')
  return (
    <Dialog>
      <DialogHeader>
        <DialogTitle>Add Account</DialogTitle>
      </DialogHeader>
      <DialogTrigger asChild>
        <button className="btn btn-primary">Add Account</button>
      </DialogTrigger>
      <DialogContent></DialogContent>
      <DialogFooter className="sm:justify-start">
        <DialogClose asChild>
          <button className="btn btn-secondary">Close</button>
        </DialogClose>
      </DialogFooter>
    </Dialog>
  )
}

export default AddAccountDialog
