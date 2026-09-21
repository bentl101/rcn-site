# RCN Tern intake — 21 September 2026

## Completed and verified

- Form: **RCN Website Lead Intake**, Trip Request type, ID `693482`.
- Owner/advisor: **Rejoice Shalom Agtagma**, River Cruise Network.
- Editor: https://app.tern.travel/forms/693482/edit
- Public intake: https://app.tern.travel/public/forms/la-CY6VegArVsIrnaQuuLA/responses/new
- Creates a contact and a trip in **New Lead - For Assignment**.
- The unused default terms question was removed with Ben's explicit confirmation. No e-signature question was added. The original client quote form was not edited.
- All fields below were verified on a submitted synthetic test response.
- Existing production n8n, email, Google Ads and Zoho routing has not been changed. Automatic forwarding is **not live**.

## Field mapping

| Existing lead field | Tern field | Mapping / requirement |
| --- | --- | --- |
| generated title | Trip Info | Required; use a short enquiry summary. Tern appends the primary contact surname to the trip title. |
| `first_name` | Legal First Name | Required by Tern. Preserve supplied text. |
| `last_name` | Last Name | Required by Tern. The RCN website allows this to be absent; a forwarder must route missing surnames for review rather than invent one. |
| `email` | Email | Required; contact field. |
| `phone` | Phone | Optional; contact field. Preserve the supplied number. |
| `destination` | Preferred itinerary or destination | Optional short text; question `4373321`. |
| `travel_date` | Preferred travel month (YYYY-MM) | Required short text; question `4373921`. Keep month precision. |
| `duration` | Trip duration | Required short text; question `4374040`. |
| `guests` | Number of guests | Required short text; question `4374042`. Preserve ranges such as `3-4` or `5+`. |
| `budget` | Budget per person (CAD range) | Required short text; question `4374043`. Preserve the original range. |
| `operator` | Preferred cruise line / operator | Required short text; question `4374044`. |
| `lead_order_id` | Lead order ID | Required short text; question `4374758`. This is a reference, not a native Tern uniqueness constraint. |
| `additional_info` | Additional information / special requests | Optional long text; question `4374554`. |
| source, timestamp, attribution, score | Lead source, submitted time and quality score | Required long text; question `4375254`. Suggested labelled lines: website, page source, submitted time, score, decision, source/medium/campaign and original lead reference. Only forward relevant metadata; no credentials. |

Set native Trip Dates to **I'm flexible with dates** when only a month is known. The verified response retains blank exact start/end dates. The automatically created itinerary displays a default seven-day duration; the authoritative original duration is in the form response until an advisor plans the itinerary.

## Verification record

- Lead reference: `RCN-TEST-20260921-TERN-001`.
- Contact: **RCN Intake Test Only**, reserved test address `rcn-intake-test-20260921@example.com` and fictional phone `+1 416 555 0100`.
- Trip: https://app.tern.travel/trips/8018221
- Contact: https://app.tern.travel/contacts/4280107
- Response: https://app.tern.travel/trips/8018221/form_responses/21423287
- Browser displayed successful sharing with Rejoice Shalom Agtagma.
- Board showed the test trip under **New Lead - For Assignment**.
- Trip overview confirmed Shalom as owner, CAD currency, and a link to the submitted form.
- Response read-back confirmed every test answer, including preferred month `2027-05`, guest count `2`, original budget range, notes and reference.
- Test was submitted directly to Tern, not via RCN or n8n; it did not enter the Google Ads upload path.
- The labelled test contact/trip remains available for review.

## Handoff to an advisor

On the trip Overview, add the chosen agency advisor as a collaborator, then use their menu > **Transfer ownership** and choose the receiving status. Contact ownership is separately managed on the contact's About tab.

Tern documents that transferring a trip deactivates existing automations, and the new owner's workflows do not automatically apply at the instant of transfer. Verify the assigned advisor's next step before relying on follow-up emails.

- https://help.tern.travel/en/articles/10201976-trip-ownership-reassignment
- https://help.tern.travel/en/articles/10770631-contact-ownership-reassignment

The inspected Starter Lead Workflow (`70285`) has auto-apply off. Tern also displays a request to re-authenticate the email/scheduler connection. Neither setting was changed.

## Automatic forwarding: remaining dependency

An unauthenticated HTTP GET of the public intake returned HTTP 200 but **no input form**. The returned page instead contains Tern's `forms--responses--gate--turnstile` controller and Cloudflare Turnstile verification. Do not treat this HTTP 200 as evidence that an n8n form POST is supported. No verification mechanism was bypassed or reverse-engineered.

The browser's normal form flow succeeded. This establishes interactive submission only; it does not establish unattended server automation. Before deploying a forwarder, obtain Tern's supported external submission/integration route or test a permitted browser worker through the normal form flow. Do not copy a logged-in browser session into server code or weaken verification.

A production forwarder also needs a durable delivery record keyed by `lead_order_id`, retry handling that checks uncertain submissions before resending, and an alert/manual queue for missing required data or verification failures. Tern does not enforce uniqueness on the reference question. Decide explicitly which scoring decisions to forward; this work has not activated a quality filter or imported historical leads.
