import os
import numpy as np
import sys
os.environ['KMP_DUPLICATE_LIB_OK']='True'
dirName = os.path.dirname(__file__)
sys.path.append(os.path.join(dirName, '..', '..', '..'))
sys.path.append(os.path.join(dirName, '..', '..'))
sys.path.append(os.path.join(dirName, '..'))


from src.ddpg import actByPolicyTrain,BuildActorModel
from src.policy import ActDDPGOneStep
from environment.chasingEnv.reward import GetActionCost, RewardFunctionCompete, RewardWithActionCost
from environment.chasingEnv.chasingPolicy import HeatSeekingContinuousDeterministicPolicy
from environment.chasingEnv.envNoPhysics import Reset, TransitForNoPhysics, getIntendedNextState, StayWithinBoundary, \
    TransitWithSingleWolf, GetAgentPosFromState, IsTerminal
from functionTools.trajectory import SampleTrajectory
from environment.chasingEnv.continuousChasingVisualization import initializeScreen, Observe, ScaleTrajectory,\
    AdjustDfFPStoTraj, DrawBackground, DrawState, ChaseTrialWithTraj
from pygame.color import THECOLORS
from functionTools.loadSaveModel import restoreVariables

maxRunningSteps = 100


def main():
    numAgents = 2
    stateDim = numAgents * 2
    actionLow = -1
    actionHigh = 1
    actionBound = (actionHigh - actionLow)/2
    actionDim = 2

    buildActorModel = BuildActorModel(stateDim, actionDim, actionBound)
    actorLayerWidths = [64]
    actorWriter, actorModel = buildActorModel(actorLayerWidths)

    dirName = os.path.dirname(__file__)
    actorModelPath = os.path.join(dirName, '..', '..', 'trainedDDPGModels', 'wolfAvoidBoundaryActionCost', 'resetSheepOnly',
                                  'actorModel=0_dimension=2_gamma=0.95_learningRateActor=0.001_learningRateCritic=0.001_maxEpisode=10000_maxTimeStep=100_minibatchSize=32_wolfSpeed=0.1.ckpt')
                                  # 'actorModel=0_dimension=2_gamma=0.95_learningRateActor=0.001_learningRateCritic=0.001_maxEpisode=20000_maxTimeStep=100_minibatchSize=32_wolfSpeed=0.1.ckpt')

    restoreVariables(actorModel, actorModelPath)
    sheepPolicy = ActDDPGOneStep(actionLow, actionHigh, actByPolicyTrain, actorModel, getNoise = None)

    sheepId = 0
    wolfId = 1
    getSheepPos = GetAgentPosFromState(sheepId)
    getWolfPos = GetAgentPosFromState(wolfId)

    wolfSpeed = 0.1
    wolfPolicy = HeatSeekingContinuousDeterministicPolicy(getWolfPos, getSheepPos, wolfSpeed)

    xBoundary = (0, 20)
    yBoundary = (0, 20)
    stayWithinBoundary = StayWithinBoundary(xBoundary, yBoundary)
    transit = TransitForNoPhysics(getIntendedNextState, stayWithinBoundary)

    sheepAliveBonus = 1
    sheepTerminalPenalty = 20

    killzoneRadius = 1
    isTerminal = IsTerminal(getWolfPos, getSheepPos, killzoneRadius)
    rewardSheep = RewardFunctionCompete(sheepAliveBonus, sheepTerminalPenalty, isTerminal)
    actionCostRate = 0.5
    getActionCost = GetActionCost(actionCostRate)
    rewardWithActionCost = RewardWithActionCost(rewardSheep, getActionCost)

    getSheepAction = lambda actions: [actions[sheepId* actionDim], actions[sheepId* actionDim+ 1]]
    getReward = lambda state, action, nextState: rewardWithActionCost(state, getSheepAction(action), nextState)

    policy = lambda state: list(sheepPolicy(state)) + list(wolfPolicy(state))
    # reset = Reset(xBoundary, yBoundary, numAgents)
    resetSheepOnly = Reset(xBoundary, yBoundary, numOfAgent = 1)
    reset = lambda: list(resetSheepOnly()) +[10, 10]

    for i in range(1):
        sampleTrajectory = SampleTrajectory(maxRunningSteps, transit, isTerminal, getReward, reset)
        trajectory = sampleTrajectory(policy)

        # plots& plot
        showDemo = True
        if showDemo:
            observe = Observe(trajectory, numAgents)

            fullScreen = False
            screenWidth = 800
            screenHeight = 800
            screen = initializeScreen(fullScreen, screenWidth, screenHeight)

            leaveEdgeSpace = 200
            lineWidth = 3
            xBoundary = [leaveEdgeSpace, screenWidth - leaveEdgeSpace * 2]
            yBoundary = [leaveEdgeSpace, screenHeight - leaveEdgeSpace * 2]
            screenColor = THECOLORS['black']
            lineColor = THECOLORS['white']

            drawBackground = DrawBackground(screen, screenColor, xBoundary, yBoundary, lineColor, lineWidth)
            circleSize = 10
            positionIndex = [0, 1]
            drawState = DrawState(screen, circleSize, positionIndex, drawBackground)

            numberOfAgents = 2
            chasingColors = [THECOLORS['green'], THECOLORS['red']]
            colorSpace = chasingColors[: numberOfAgents]

            FPS = 60
            chaseTrial = ChaseTrialWithTraj(FPS, colorSpace, drawState, saveImage=True)

            rawXRange = [0, 20]
            rawYRange = [0, 20]
            scaledXRange = [210, 590]
            scaledYRange = [210, 590]
            scaleTrajectory = ScaleTrajectory(positionIndex, rawXRange, rawYRange, scaledXRange, scaledYRange)

            oldFPS = 60
            adjustFPS = AdjustDfFPStoTraj(oldFPS, FPS)

            getTrajectory = lambda rawTrajectory: scaleTrajectory(adjustFPS(rawTrajectory))
            positionList = [observe(index) for index in range(len(trajectory))]
            positionListToDraw = getTrajectory(positionList)

            currentDir = os.getcwd()
            parentDir = os.path.abspath(os.path.join(currentDir, os.pardir))
            imageFolderName = 'Demo'
            saveImageDir = os.path.join(os.path.join(parentDir, 'chasingDemo'), imageFolderName)
            if not os.path.exists(saveImageDir):
                os.makedirs(saveImageDir)

            chaseTrial(numberOfAgents, positionListToDraw, saveImageDir)

if __name__ == '__main__':
    main()