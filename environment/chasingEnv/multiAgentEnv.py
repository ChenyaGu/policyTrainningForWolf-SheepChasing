import tensorflow as tf
import numpy as np
import os
import sys


getPosFromAgentState = lambda state: np.array([state[0], state[1]])
getVelFromAgentState = lambda state: np.array([state[2], state[3]])
getCaughtHistoryFromAgentState = lambda state: np.array(state[4])


class IsCollision:
    def __init__(self, getPosFromState):
        self.getPosFromState = getPosFromState

    def __call__(self, agent1State, agent2State, agent1Size, agent2Size):
        posDiff = self.getPosFromState(agent1State) - self.getPosFromState(agent2State)
        dist = np.sqrt(np.sum(np.square(posDiff)))
        minDist = agent1Size + agent2Size
        return True if dist < minDist else False


class RewardWolf:
    def __init__(self, wolvesID, sheepsID, entitiesSizeList, isCollision, collisionReward=10):
        self.wolvesID = wolvesID
        self.sheepsID = sheepsID
        self.entitiesSizeList = entitiesSizeList
        self.isCollision = isCollision
        self.collisionReward = collisionReward

    def __call__(self, state, action, nextState):
        wolfReward = 0
        for wolfID in self.wolvesID:
            wolfSize = self.entitiesSizeList[wolfID]
            wolfNextState = nextState[wolfID]
            for sheepID in self.sheepsID:
                sheepSize = self.entitiesSizeList[sheepID]
                sheepNextState = nextState[sheepID]

                if self.isCollision(wolfNextState, sheepNextState, wolfSize, sheepSize):
                    wolfReward += self.collisionReward
        reward = [wolfReward] * len(self.wolvesID)
        # print('wolfreward ', wolfReward)
        return reward


class RewardWolfWithBiteAndKill:
    def __init__(self, wolvesID, sheepsID, entitiesSizeList, isCollision, getCaughtHistoryFromAgentState, sheepLife=10,
                 biteReward=0.01, killReward=1):
        self.wolvesID = wolvesID
        self.sheepsID = sheepsID
        self.entitiesSizeList = entitiesSizeList
        self.isCollision = isCollision
        self.getEntityCaughtHistory = lambda state, entityID: getCaughtHistoryFromAgentState(state[entityID])
        self.sheepLife = sheepLife
        self.biteReward = biteReward
        self.killReward = killReward

    def __call__(self, state, action, nextState):
        wolfReward = 0
        for wolfID in self.wolvesID:
            wolfSize = self.entitiesSizeList[wolfID]
            wolfNextState = nextState[wolfID]
            for sheepID in self.sheepsID:
                sheepSize = self.entitiesSizeList[sheepID]
                sheepNextState = nextState[sheepID]
                if self.isCollision(wolfNextState, sheepNextState, wolfSize, sheepSize):
                    wolfReward += self.biteReward
                sheepCaughtHistory = self.getEntityCaughtHistory(state, sheepID)
                if sheepCaughtHistory == self.sheepLife:
                    wolfReward += self.killReward

        reward = [wolfReward] * len(self.wolvesID)
        return reward


class ContinuousHuntingRewardWolf:
    def __init__(self, wolvesID, sheepsID, entitiesSizeList, isCollision, sheepLife=3, collisionReward=10):
        self.wolvesID = wolvesID
        self.sheepsID = sheepsID
        self.entitiesSizeList = entitiesSizeList
        self.isCollision = isCollision
        self.collisionReward = collisionReward
        self.sheepLife = sheepLife
        self.getCaughtHistory = {sheepID: 0 for sheepID in sheepsID}
    def __call__(self, state, action, nextState):
        wolfReward = 0                    
        for sheepID in self.sheepsID:
            sheepSize = self.entitiesSizeList[sheepID]
            sheepNextState = nextState[sheepID]
            getCaught = 0
            for wolfID in self.wolvesID:
                wolfSize = self.entitiesSizeList[wolfID]
                wolfNextState = nextState[wolfID]
                if self.isCollision(wolfNextState, sheepNextState, wolfSize, sheepSize):
                    self.getCaughtHistory[sheepID] += 1
                    getCaught = 1
                    break
            if not getCaught:
                self.getCaughtHistory[sheepID] = 0
        for sheepID in self.sheepsID:
            if self.getCaughtHistory[sheepID] == self.sheepLife:
                wolfReward += self.collisionReward
                self.getCaughtHistory[sheepID] = 0
        reward = [wolfReward] * len(self.wolvesID)
        return reward


class PunishForOutOfBound:
    def __init__(self):
        self.physicsDim = 2

    def __call__(self, agentPos):
        punishment = 0
        for i in range(self.physicsDim):
            x = abs(agentPos[i])
            punishment += self.bound(x)
        return punishment

    def bound(self, x):
        if x < 0.9:
            return 0
        if x < 1.0:
            return (x - 0.9) * 10
        return min(np.exp(2 * x - 2), 10)
        # if x < 1.0:
        #     return 0
        # if x < 1.1:
        #     return (x - 1.0) * 10
        # return min(np.exp(2 * x - 2.2), 10)


class RewardSheep:
    def __init__(self, wolvesID, sheepsID, entitiesSizeList, getPosFromState, isCollision, punishForOutOfBound,
                 collisionPunishment=10):
        self.wolvesID = wolvesID
        self.getPosFromState = getPosFromState
        self.entitiesSizeList = entitiesSizeList
        self.sheepsID = sheepsID
        self.isCollision = isCollision
        self.collisionPunishment = collisionPunishment
        self.punishForOutOfBound = punishForOutOfBound

    def __call__(self, state, action, nextState): #state, action not used
        reward = []
        for sheepID in self.sheepsID:
            sheepReward = 0
            sheepNextState = nextState[sheepID]
            sheepNextPos = self.getPosFromState(sheepNextState)
            sheepSize = self.entitiesSizeList[sheepID]

            sheepReward -= self.punishForOutOfBound(sheepNextPos)
            for wolfID in self.wolvesID:
                wolfSize = self.entitiesSizeList[wolfID]
                wolfNextState = nextState[wolfID]
                if self.isCollision(wolfNextState, sheepNextState, wolfSize, sheepSize):
                    sheepReward -= self.collisionPunishment
            reward.append(sheepReward)
        return reward


class RewardSheepWithBiteAndKill:
    def __init__(self, wolvesID, sheepsID, entitiesSizeList, getPosFromState, isCollision, punishForOutOfBound,
                 getCaughtHistoryFromAgentState, sheepLife=10, bitePunishment=0.01, killPunishment=1):
        self.wolvesID = wolvesID
        self.sheepsID = sheepsID
        self.entitiesSizeList = entitiesSizeList
        self.getPosFromState = getPosFromState
        self.isCollision = isCollision
        self.punishForOutOfBound = punishForOutOfBound
        self.getEntityCaughtHistory = lambda state, entityID: getCaughtHistoryFromAgentState(state[entityID])
        self.sheepLife = sheepLife
        self.bitePunishment = bitePunishment
        self.killPunishment = killPunishment

    def __call__(self, state, action, nextState): #state, action not used
        reward = []
        for sheepID in self.sheepsID:
            sheepReward = 0
            sheepNextState = nextState[sheepID]
            sheepNextPos = self.getPosFromState(sheepNextState)
            sheepReward -= self.punishForOutOfBound(sheepNextPos)
            sheepSize = self.entitiesSizeList[sheepID]

            for wolfID in self.wolvesID:
                wolfSize = self.entitiesSizeList[wolfID]
                wolfNextState = nextState[wolfID]
                if self.isCollision(wolfNextState, sheepNextState, wolfSize, sheepSize):
                    sheepReward -= self.bitePunishment
                sheepCaughtHistory = self.getEntityCaughtHistory(state, sheepID)
                if sheepCaughtHistory == self.sheepLife:
                    sheepReward -= self.killPunishment
            reward.append(sheepReward)
        return reward


class ContinuousHuntingRewardSheep:
    def __init__(self, wolvesID, sheepsID, entitiesSizeList, getPosFromState, isCollision, punishForOutOfBound,
                 sheepLife=3, collisionPunishment=10):
        self.wolvesID = wolvesID
        self.sheepsID = sheepsID
        self.entitiesSizeList = entitiesSizeList
        self.getPosFromState = getPosFromState
        self.isCollision = isCollision
        self.punishForOutOfBound = punishForOutOfBound
        self.sheepLife = sheepLife
        self.collisionPunishment = collisionPunishment
        self.getCaughtHistory = {sheepId: 0 for sheepId in sheepsID}
    def __call__(self, state, action, nextState): #state, action not used
        reward = []
        for sheepID in self.sheepsID:
            sheepSize = self.entitiesSizeList[sheepID]
            sheepNextState = nextState[sheepID]
            sheepNextPos = self.getPosFromState(sheepNextState)
            getCaught = 0
            sheepReward = 0
            sheepReward -= self.punishForOutOfBound(sheepNextPos)
            for wolfID in self.wolvesID:
                wolfSize = self.entitiesSizeList[wolfID]
                wolfNextState = nextState[wolfID]
                if self.isCollision(wolfNextState, sheepNextState, wolfSize, sheepSize):
                    self.getCaughtHistory[sheepID] += 1
                    getCaught = 1
                    break
            if not getCaught:
                self.getCaughtHistory[sheepID] = 0
            if self.getCaughtHistory[sheepID] == self.sheepLife:
                sheepReward -= self.collisionPunishment
                self.getCaughtHistory[sheepID] = 0
            reward.append(sheepReward)
        return reward


class CalSheepCaughtHistory:
    def __init__(self, wolvesID, sheepsID, entitiesSizeList, isCollision, sheepLife=10):
        self.wolvesID = wolvesID
        self.sheepsID = sheepsID
        self.entitiesSizeList = entitiesSizeList
        self.isCollision = isCollision
        self.sheepLife = sheepLife
        self.getCaughtHistory = {sheepId: 0 for sheepId in sheepsID}
    def __call__(self, state, nextState): #state not used
        for sheepID in self.sheepsID:
            sheepSize = self.entitiesSizeList[sheepID]
            sheepNextState = nextState[sheepID]
            getCaught = 0
            for wolfID in self.wolvesID:
                wolfSize = self.entitiesSizeList[wolfID]
                wolfNextState = nextState[wolfID]
                if self.isCollision(wolfNextState, sheepNextState, wolfSize, sheepSize):
                    self.getCaughtHistory[sheepID] += 1
                    getCaught = 1
                    break
            if not getCaught:
                self.getCaughtHistory[sheepID] = 0
            if self.getCaughtHistory[sheepID] == self.sheepLife+1:
                self.getCaughtHistory[sheepID] = 0
        return self.getCaughtHistory.copy()


class ResetMultiAgentChasing:
    def __init__(self, numTotalAgents, numBlocks):
        self.positionDimension = 2
        self.numTotalAgents = numTotalAgents
        self.numBlocks = numBlocks
    def __call__(self):
        getAgentRandomPos = lambda: np.random.uniform(-1, +1, self.positionDimension)
        getAgentRandomVel = lambda: np.zeros(self.positionDimension)
        agentsState = [list(getAgentRandomPos()) + list(getAgentRandomVel()) for ID in range(self.numTotalAgents)]
        getBlockRandomPos = lambda: np.random.uniform(-0.9, +0.9, self.positionDimension)
        getBlockSpeed = lambda: np.zeros(self.positionDimension)
        blocksState = [list(getBlockRandomPos()) + list(getBlockSpeed()) for blockID in range(self.numBlocks)]
        state = np.array(agentsState + blocksState)
        return state


class ResetMultiAgentChasingWithCaughtHistory:
    def __init__(self, numTotalAgents, numBlocks):
        self.positionDimension = 2
        self.numTotalAgents = numTotalAgents
        self.numBlocks = numBlocks
    def __call__(self):
        getAgentRandomPos = lambda: np.random.uniform(-1.0, +1.0, self.positionDimension)
        getAgentRandomVel = lambda: np.zeros(self.positionDimension)
        agentsState = [list(getAgentRandomPos()) + list(getAgentRandomVel()) for ID in range(self.numTotalAgents)]
        getBlockRandomPos = lambda: np.random.uniform(-0.6, +0.6, self.positionDimension)
        getBlockSpeed = lambda: np.zeros(self.positionDimension)
        # Obstacles overlap detection
        # The distance between obstacles should at least accommodate 2 agents (wolves/sheep)
        while self.numBlocks:
            initBlockPos = [list(getBlockRandomPos()) for blockID in range(self.numBlocks)]
            posDiff = list(map(lambda x: x[0] - x[1], zip(initBlockPos[0], initBlockPos[1])))
            dist = np.sqrt(np.sum(np.square(posDiff)))
            if dist > (0.26*2 + 0.065*8):
                break
        blocksState = [initBlockPos[blockID] + list(getBlockSpeed()) for blockID in range(self.numBlocks)]
        # blocksState = [list(getBlockRandomPos()) + list(getBlockSpeed()) for blockID in range(2)]
        state = agentsState + blocksState
        agentInitCaughtHistory = 0
        for agentState in state:
            agentState.append(agentInitCaughtHistory)
        state = np.array(state)
        return state


class ResetStateWithCaughtHistory:
    def __init__(self, resetState, calSheepCaughtHistory):
        self.resetState = resetState
        self.calSheepCaughtHistory = calSheepCaughtHistory
    def __call__(self):
        self.calSheepCaughtHistory.getCaughtHistory = {sheepId: 0 for sheepId in self.calSheepCaughtHistory.sheepsID}
        return self.resetState()


class ResetStateAndReward:
    def __init__(self, resetState, rewardWolf, rewardSheep):
        self.resetState = resetState
        self.rewardWolf = rewardWolf
        self.rewardSheep = rewardSheep
    def __call__(self):
        self.rewardWolf.getCaughtHistory = {sheepId: 0 for sheepId in self.rewardWolf.sheepsID}
        self.rewardSheep.getCaughtHistory = {sheepId: 0 for sheepId in self.rewardSheep.sheepsID}
        return self.resetState()


class Observe:
    def __init__(self, agentID, wolvesID, sheepsID, blocksID, getPosFromState, getVelFromAgentState):
        self.agentID = agentID
        self.wolvesID = wolvesID
        self.sheepsID = sheepsID
        self.blocksID = blocksID
        self.getEntityPos = lambda state, entityID: getPosFromState(state[entityID])
        self.getEntityVel = lambda state, entityID: getVelFromAgentState(state[entityID])

    def __call__(self, state):
        blocksPos = [self.getEntityPos(state, blockID) for blockID in self.blocksID]
        agentPos = self.getEntityPos(state, self.agentID)
        blocksInfo = [blockPos - agentPos for blockPos in blocksPos]

        posInfo = []
        for wolfID in self.wolvesID:
            if wolfID == self.agentID: continue
            wolfPos = self.getEntityPos(state, wolfID)
            posInfo.append(wolfPos - agentPos)

        velInfo = []
        for sheepID in self.sheepsID:
            if sheepID == self.agentID: continue
            sheepPos = self.getEntityPos(state, sheepID)
            posInfo.append(sheepPos - agentPos)
            sheepVel = self.getEntityVel(state, sheepID)
            velInfo.append(sheepVel)

        agentVel = self.getEntityVel(state, self.agentID)
        # print(self.agentID,self.sheepsID,'state:', state)
        # print(self.agentID,self.sheepsID,'agentVel:' ,agentVel, 'agentPos:' ,agentPos, 'blocksInfo:' ,blocksInfo, 'posInfo:' ,posInfo, 'velInfo:' ,velInfo)
        return np.concatenate([agentVel] + [agentPos] + blocksInfo + posInfo + velInfo)


class ObserveWithCaughtHistory:
    def __init__(self, agentID, wolvesID, sheepsID, blocksID, getPosFromAgentState, getVelFromAgentState,
                 getCaughtHistoryFromAgentState):
        self.agentID = agentID
        self.wolvesID = wolvesID
        self.sheepsID = sheepsID
        self.blocksID = blocksID
        self.getEntityPos = lambda state, entityID: getPosFromAgentState(state[entityID])
        self.getEntityVel = lambda state, entityID: getVelFromAgentState(state[entityID])
        self.getEntityCaughtHistory = lambda state, entityID: getCaughtHistoryFromAgentState(state[entityID])

    def __call__(self, state):
        agentPos = self.getEntityPos(state, self.agentID)
        agentVel = self.getEntityVel(state, self.agentID)
        blocksPos = [self.getEntityPos(state, blockID) for blockID in self.blocksID]
        blocksInfo = [blockPos - agentPos for blockPos in blocksPos]

        posInfo = []
        for wolfID in self.wolvesID:
            if wolfID == self.agentID: continue
            wolfPos = self.getEntityPos(state, wolfID)
            posInfo.append(wolfPos - agentPos)

        velInfo = []
        caughtInfo = []
        for sheepID in self.sheepsID:
            if sheepID == self.agentID: continue
            sheepPos = self.getEntityPos(state, sheepID)
            posInfo.append(sheepPos - agentPos)
            sheepVel = self.getEntityVel(state, sheepID)
            velInfo.append(sheepVel)
            sheepCaughtHistory = self.getEntityCaughtHistory(state, sheepID)
            caughtInfo.append([sheepCaughtHistory])

        return np.concatenate([agentVel] + [agentPos] + blocksInfo + posInfo + velInfo + caughtInfo)


class GetCollisionForce:
    def __init__(self, contactMargin = 0.001, contactForce = 100):
        self.contactMargin = contactMargin
        self.contactForce = contactForce

    def __call__(self, obj1Pos, obj2Pos, obj1Size, obj2Size, obj1Movable, obj2Movable):
        posDiff = obj1Pos - obj2Pos
        dist = np.sqrt(np.sum(np.square(posDiff)))

        minDist = obj1Size + obj2Size
        penetration = np.logaddexp(0, -(dist - minDist) / self.contactMargin) * self.contactMargin

        force = self.contactForce* posDiff / dist * penetration
        force1 = +force if obj1Movable else None
        force2 = -force if obj2Movable else None

        return [force1, force2]


class ApplyActionForce:
    def __init__(self, wolvesID, sheepsID, entitiesMovableList, actionDim=2):
        self.agentsID = sheepsID + wolvesID
        self.numAgents = len(self.agentsID)
        self.entitiesMovableList = entitiesMovableList
        self.actionDim = actionDim

    def __call__(self, pForce, actions):
        noise = [None] * self.numAgents
        for agentID in self.agentsID:
            movable = self.entitiesMovableList[agentID]
            agentNoise = noise[agentID]
            if movable:
                agentNoise = np.random.randn(self.actionDim) * agentNoise if agentNoise else 0.0
                pForce[agentID] = np.array(actions[agentID]) + agentNoise
        return pForce


class ApplyEnvironForce:
    def __init__(self, numEntities, entitiesMovableList, entitiesSizeList, getCollisionForce, getPosFromState):
        self.numEntities = numEntities
        self.entitiesMovableList = entitiesMovableList
        self.entitiesSizeList = entitiesSizeList
        self.getCollisionForce = getCollisionForce
        self.getEntityPos = lambda state, entityID: getPosFromState(state[entityID])

    def __call__(self, pForce, state):
        for entity1ID in range(self.numEntities):
            for entity2ID in range(self.numEntities):
                if entity2ID <= entity1ID: continue
                obj1Movable = self.entitiesMovableList[entity1ID]
                obj2Movable = self.entitiesMovableList[entity2ID]
                obj1Size = self.entitiesSizeList[entity1ID]
                obj2Size = self.entitiesSizeList[entity2ID]
                obj1Pos = self.getEntityPos(state, entity1ID)
                obj2Pos = self.getEntityPos(state, entity2ID)

                force1, force2 = self.getCollisionForce(obj1Pos, obj2Pos, obj1Size, obj2Size, obj1Movable, obj2Movable)

                if force1 is not None:
                    if pForce[entity1ID] is None: pForce[entity1ID] = 0.0
                    pForce[entity1ID] = force1 + pForce[entity1ID]

                if force2 is not None:
                    if pForce[entity2ID] is None: pForce[entity2ID] = 0.0
                    pForce[entity2ID] = force2 + pForce[entity2ID]
        return pForce


class IntegrateState:
    def __init__(self, numEntities, entitiesMovableList, massList, entityMaxSpeedList,  getVelFromAgentState, getPosFromAgentState,
                 damping=0.25, dt=0.2):
        self.numEntities = numEntities
        self.entitiesMovableList = entitiesMovableList
        self.damping = damping
        self.dt = dt
        self.massList = massList
        self.entityMaxSpeedList = entityMaxSpeedList
        self.getEntityVel = lambda state, entityID: getVelFromAgentState(state[entityID])
        self.getEntityPos = lambda state, entityID: getPosFromAgentState(state[entityID])

    def __call__(self, pForce, state):
        getNextState = lambda entityPos, entityVel: list(entityPos) + list(entityVel)
        nextState = []
        for entityID in range(self.numEntities):
            entityMovable = self.entitiesMovableList[entityID]
            entityVel = self.getEntityVel(state, entityID)
            entityPos = self.getEntityPos(state, entityID)

            if not entityMovable:
                nextState.append(getNextState(entityPos, entityVel))
                continue

            entityNextVel = entityVel * (1 - self.damping)
            entityForce = pForce[entityID]
            entityMass = self.massList[entityID]
            if entityForce is not None:
                entityNextVel += (entityForce / entityMass) * self.dt

            entityMaxSpeed = self.entityMaxSpeedList[entityID]
            if entityMaxSpeed is not None:
                speed = np.sqrt(np.square(entityVel[0]) + np.square(entityVel[1]))
                if speed > entityMaxSpeed:
                    entityNextVel = entityNextVel / speed * entityMaxSpeed

            entityNextPos = entityPos + entityNextVel * self.dt
            nextState.append(getNextState(entityNextPos, entityNextVel))

        return nextState


class IntegrateStateWithCaughtHistory:
    def __init__(self, numEntities, entitiesMovableList, massList, entityMaxSpeedList,  getVelFromAgentState, getPosFromAgentState,
                 calSheepCaughtHistory, damping=0.25, dt=0.05):
        self.numEntities = numEntities
        self.entitiesMovableList = entitiesMovableList
        self.damping = damping
        self.dt = dt
        self.massList = massList
        self.entityMaxSpeedList = entityMaxSpeedList
        self.getEntityVel = lambda state, entityID: getVelFromAgentState(state[entityID])
        self.getEntityPos = lambda state, entityID: getPosFromAgentState(state[entityID])
        self.calSheepCaughtHistory = calSheepCaughtHistory

    def __call__(self, pForce, state):
        getNextState = lambda entityPos, entityVel: list(entityPos) + list(entityVel)
        nextState = []
        sheepsID = self.calSheepCaughtHistory.sheepsID
        for entityID in range(self.numEntities):
            entityMovable = self.entitiesMovableList[entityID]
            entityVel = self.getEntityVel(state, entityID)
            entityPos = self.getEntityPos(state, entityID)

            if not entityMovable:
                nextState.append(getNextState(entityPos, entityVel))
                continue

            entityNextVel = entityVel * (1 - self.damping)
            entityForce = pForce[entityID]
            entityMass = self.massList[entityID]
            if entityForce is not None:
                entityNextVel += (entityForce / entityMass) * self.dt

            entityMaxSpeed = self.entityMaxSpeedList[entityID]
            if entityMaxSpeed is not None:
                speed = np.sqrt(np.square(entityVel[0]) + np.square(entityVel[1]))
                if speed > entityMaxSpeed:
                    entityNextVel = entityNextVel / speed * entityMaxSpeed

            entityNextPos = entityPos + entityNextVel * self.dt
            nextState.append(getNextState(entityNextPos, entityNextVel))
        caughtHistory = self.calSheepCaughtHistory(state, nextState)
        for sheepID in sheepsID:
            nextState[sheepID].append(caughtHistory[sheepID])
        nextStateWithCaughtHistory = nextState.copy()
        return nextStateWithCaughtHistory


class TransitMultiAgentChasing:
    def __init__(self, numEntities, reshapeAction, applyActionForce, applyEnvironForce, integrateState):
        self.numEntities = numEntities
        self.reshapeAction = reshapeAction
        self.applyActionForce = applyActionForce
        self.applyEnvironForce = applyEnvironForce
        self.integrateState = integrateState

    def __call__(self, state, actions):

        actions = [self.reshapeAction(action) for action in actions]
        # print('action', actions[0], actions[1])
        # print('wolfaction', actions[0])

        p_force = [None] * self.numEntities
        p_force = self.applyActionForce(p_force, actions)
        p_force = self.applyEnvironForce(p_force, state)
        nextState = self.integrateState(p_force, state)

        return nextState


class TransitMultiAgentChasingVariousForce:
    def __init__(self, numEntities, reshapeAction, applyActionForce, applyEnvironForce, integrateState):
        self.numEntities = numEntities
        self.reshapeAction = reshapeAction
        self.applyActionForce = applyActionForce
        self.applyEnvironForce = applyEnvironForce
        self.integrateState = integrateState

    def __call__(self, state, actions):
        wolfAction = [self.reshapeAction(actions[i], 5) for i in range(3)]
        sheepAction = [self.reshapeAction(actions[i], 6) for i in range(3, len(actions))]
        actions = wolfAction + sheepAction
        # print('action', actions[0], actions[1])
        # print('wolfaction', actions[0])

        p_force = [None] * self.numEntities
        p_force = self.applyActionForce(p_force, actions)
        p_force = self.applyEnvironForce(p_force, state)
        nextState = self.integrateState(p_force, state)

        return nextState


class ReshapeAction:
    def __init__(self):
        self.actionDim = 2
        self.sensitivity = 5

    def __call__(self, action): # action: tuple of dim (5,1)
        # print(action)
        actionX = action[1] - action[2]
        actionY = action[3] - action[4]
        actionReshaped = np.array([actionX, actionY]) * self.sensitivity
        return actionReshaped


class ReshapeActionVariousForce:
    def __init__(self):
        self.actionDim = 2
        # self.sensitivity = 5

    def __call__(self, action, sensitivity):  # action: tuple of dim (5,1)
        actionX = action[1] - action[2]
        actionY = action[3] - action[4]
        actionReshaped = np.array([actionX, actionY]) * sensitivity
        return actionReshaped
