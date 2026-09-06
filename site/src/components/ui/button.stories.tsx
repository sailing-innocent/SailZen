import type { Meta, StoryObj } from "@storybook/react";
import { Button } from "./button";
import { Plus, ArrowRight, Check, Search } from "lucide-react";

const meta = {
  title: "UI/Button",
  component: Button,
  parameters: {
    layout: "centered",
  },
  tags: ["autodocs"],
  args: {
    children: "Button",
    variant: "default",
    size: "default",
  },
  argTypes: {
    variant: {
      control: { type: "select" },
      options: [
        "default",
        "destructive",
        "outline",
        "secondary",
        "ghost",
        "link",
      ],
    },
    size: {
      control: { type: "select" },
      options: ["sm", "default", "lg", "icon"],
    },
    onClick: { action: "clicked" },
  },
} satisfies Meta<typeof Button>;

export default meta;

type Story = StoryObj<typeof meta>;

export const Default: Story = {};
export const Destructive: Story = { args: { variant: "destructive" } };
export const Outline: Story = { args: { variant: "outline" } };
export const Secondary: Story = { args: { variant: "secondary" } };
export const Ghost: Story = { args: { variant: "ghost" } };
export const Link: Story = { args: { variant: "link" } };

// Sizes
export const Small: Story = { args: { size: "sm" } };
export const Large: Story = { args: { size: "lg" } };
export const IconButton: Story = {
  args: {
    size: "icon",
    children: <Search aria-hidden />,
    "aria-label": "Search",
  },
};

// With icons
export const WithLeftIcon: Story = {
  args: {
    children: (
      <>
        <Plus />
        Add Item
      </>
    ),
  },
};

export const WithRightIcon: Story = {
  args: {
    children: (
      <>
        Continue
        <ArrowRight />
      </>
    ),
  },
};

export const SuccessStateMock: Story = {
  name: "With success icon",
  args: {
    children: (
      <>
        <Check />
        Saved
      </>
    ),
    variant: "secondary",
  },
};

// Disabled & full width
export const Disabled: Story = { args: { disabled: true } };
export const FullWidth: Story = {
  args: { className: "w-full" },
  parameters: { layout: "padded" },
};

// asChild example (anchor)
export const AsChildLink: Story = {
  name: "asChild as <a>",
  args: {
    asChild: true,
    children: (
      <a href="#" onClick={(e) => e.preventDefault()}>
        Go to docs
      </a>
    ),
  },
};

// Composite grids for quick visual scan
export const AllVariants: Story = {
  render: (args) => (
    <div className="flex flex-col gap-3">
      <div className="flex items-center gap-2 flex-wrap">
        <Button {...args} variant="default">Default</Button>
        <Button {...args} variant="destructive">Destructive</Button>
        <Button {...args} variant="outline">Outline</Button>
        <Button {...args} variant="secondary">Secondary</Button>
        <Button {...args} variant="ghost">Ghost</Button>
        <Button {...args} variant="link">Link</Button>
      </div>
    </div>
  ),
  parameters: { controls: { exclude: ["children"] } },
};

export const AllSizes: Story = {
  render: (args) => (
    <div className="flex items-center gap-3 flex-wrap">
      <Button {...args} size="sm">Small</Button>
      <Button {...args} size="default">Default</Button>
      <Button {...args} size="lg">Large</Button>
      <Button {...args} size="icon" aria-label="Settings">
        <Search />
      </Button>
    </div>
  ),
  parameters: { controls: { exclude: ["children"] } },
};

// Text/content edge cases
export const LongText: Story = {
  args: {
    children:
      "This is a very long label to test how the button behaves with long text",
    className: "max-w-xs",
  },
};

export const AriaInvalid: Story = {
  args: {
    children: "Invalid",
    "aria-invalid": true,
    variant: "outline",
  },
};
