# Webhook Payload Examples

## Stripe Success Payload Shape

```json
{
  "event": "checkout.session.completed",
  "customer_email": "customer@example.com",
  "customer_name": "Example Customer",
  "company": "Example Co",
  "plan": "managed-setup",
  "github_username": "optional-at-checkout",
  "deployment_path": "vercel"
}
```

## GHL Success Payload Shape

```json
{
  "event": "order.submitted",
  "contact": {
    "name": "Example Customer",
    "email": "customer@example.com"
  },
  "company": "Example Co",
  "plan": "private-server-license",
  "github_username": "optional",
  "deployment_path": "docker"
}
```

## Internal Normalized Record

```json
{
  "customer_name": "Example Customer",
  "billing_email": "customer@example.com",
  "company": "Example Co",
  "plan": "managed-setup",
  "github_username": "exampleuser",
  "deployment_path": "vercel",
  "source": "stripe",
  "status": "paid"
}
```
