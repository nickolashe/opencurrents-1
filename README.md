# openCurrents platform architecture a bird's eye overview


## Goal
We are building an alternative currency platform where users can earn "currents" for volunteering their time with non-profits. These can then be spent with businesses which post offers on the platform.

## Orgs
Architecturally, both non-profits and businesses are modeled using [Org](https://github.com/opencurrents/opencurrents/blob/develop/openCurrents/models.py#L17) model. The **status** field differentiates between the two types of organizations.

## Users
For the users we are using Django's internal auth **User** model.
Users can be affiliated with Orgs through [OrgUser](https://github.com/opencurrents/opencurrents/blob/develop/openCurrents/models.py#L50) mapping.
Some users can have admin permissions for an org, and these are modeled using Django's internal auth **Group** model. The convention is to name the group *admin_$id*, where id is the id of the organization. Any member of the group is be granted admin privileges on the respective org.

## Business logic interfaces
Much of the business logic has been separated into [interfaces](https://github.com/opencurrents/opencurrents/tree/develop/openCurrents/interfaces)

### Examples of using the interfaces

* The following method checks whether a user has admin privilege for a given org:
https://github.com/opencurrents/opencurrents/blob/develop/openCurrents/interfaces/orgs.py#L54
* Org admin can call [get_hours_approved](https://github.com/opencurrents/opencurrents/blob/develop/openCurrents/interfaces/orgadmin.py#L31) method to obtain volunteer requests pending approval
* Biz admin can call [get_redemptions](https://github.com/opencurrents/opencurrents/blob/develop/openCurrents/interfaces/bizadmin.py#L63) method to obtain offer redemption requests
