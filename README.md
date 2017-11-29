# openCurrents platform architecture - a bird's eye overview


## Goal
We are building an alternative currency platform where users can earn "currents" for volunteering their time with non-profits. Once a non-profit approves volunteer hours, these can then be spent with businesses which post offers on the platform.

## Orgs
Both non-profits and businesses are modeled using [Org](https://github.com/opencurrents/opencurrents/blob/develop/openCurrents/models.py#L17) model. The *status* field differentiates between the two types of organizations.

## Users
For the users we are using Django's internal auth *User* model.
Users can be affiliated with Orgs through [OrgUser](https://github.com/opencurrents/opencurrents/blob/develop/openCurrents/models.py#L50) mapping.
Some users can have admin permissions for an org. These are modeled using Django's internal auth *Group* model. The convention is to name the group *admin_$id*, where id is the id of the organization. Any member of the group is granted admin privileges on the respective org.

## Business logic interfaces
Much of openCurrents business logic has been separated into [interfaces](https://github.com/opencurrents/opencurrents/tree/develop/openCurrents/interfaces).

### Examples of using the interfaces

* OcUser
  * To set up a user and all the related fixtures, call:
https://github.com/opencurrents/opencurrents/blob/develop/openCurrents/interfaces/ocuser.py#L38
More on creating fixture in:
  * User's available balance in currents is composed of earned currents minus pending offer redemptions. To get user's available balance in currents call:
https://github.com/opencurrents/opencurrents/blob/develop/openCurrents/interfaces/ocuser.py#L103

  * User's pending balance in currents is equal to sum of volunteer hours request. To get user's pending balance in currents:
https://github.com/opencurrents/opencurrents/blob/develop/openCurrents/interfaces/ocuser.py#L142

  * User's available USD balance is equal to the sum of offer redemptions in *redeemed* status. To get user's available balance in USD:
https://github.com/opencurrents/opencurrents/blob/develop/openCurrents/interfaces/ocuser.py#L174

  * User's available USD balance is equal to the sum of offer redemptions in *requested* or *approved* status. To get user's pending balance in USD:
https://github.com/opencurrents/opencurrents/blob/develop/openCurrents/interfaces/ocuser.py#L187

* OcOrg
  * To set up an org and all the related fixtures, call:
https://github.com/opencurrents/opencurrents/blob/develop/openCurrents/interfaces/orgs.py#L86

* OrgUser
  * To set up an *OrgUser* mapping, call:
https://github.com/opencurrents/opencurrents/blob/develop/openCurrents/interfaces/orgs.py#L24
  * The following method checks whether a user has admin privilege for a given org:
https://github.com/opencurrents/opencurrents/blob/develop/openCurrents/interfaces/orgs.py#L54

* Organizations (non-profits) are the entities issuing currents. Approving hours volunteered for a given org by that org's admin issues currents to the volunteer.
  * [get_hours_requested](https://github.com/opencurrents/opencurrents/blob/develop/openCurrents/interfaces/orgadmin.py#L31) is a method to obtain hours volunteered for the given org that are pending approval
  * [get_hours_approved](https://github.com/opencurrents/opencurrents/blob/develop/openCurrents/interfaces/orgadmin.py#L37) is a method to obtain approved volunteer hours for the given org

* Businesses can receive currents from users in exchange for their products or services:
  * [get_balance_available](https://github.com/opencurrents/opencurrents/blob/develop/openCurrents/interfaces/bizadmin.py#L33) is a method to obtain business' available balance in currents. Available balance results from offer redemptions that have been approved.
  * [get_balance_pending](https://github.com/opencurrents/opencurrents/blob/develop/openCurrents/interfaces/bizadmin.py#L45) is a method to obtain business' pending balance in currents. Pending balance results from redemptions that have not been approved yet.
  * [get_offers_all](https://github.com/opencurrents/opencurrents/blob/develop/openCurrents/interfaces/bizadmin.py#L57) is a method to obtain all of the business' marketplace offers.
